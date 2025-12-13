"""矛盾检测API - 设定追溯与矛盾管理"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models_new import EntitySnapshot, Conflict
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.settings import Settings
from app.services_new import EntityExtractor, ConflictDetector
from app.services.ai_service import AIService, create_user_ai_service
from app.schemas.conflict import (
    ConflictResponse,
    ConflictDetailResponse,
    ConflictListResponse,
    ConflictResolveRequest
)
from app.logger import get_logger
from app.config import settings as app_settings

router = APIRouter(prefix="/conflicts", tags=["矛盾检测"])
logger = get_logger(__name__)


def _read_env_defaults() -> Dict[str, Any]:
    """从环境变量读取默认AI配置"""
    return {
        "api_provider": app_settings.default_ai_provider,
        "api_key": app_settings.openai_api_key or app_settings.anthropic_api_key or "",
        "api_base_url": app_settings.openai_base_url or app_settings.anthropic_base_url or "",
        "llm_model": app_settings.default_model,
        "temperature": app_settings.default_temperature,
        "max_tokens": app_settings.default_max_tokens,
    }


async def get_user_ai_service(user_id: str, db: AsyncSession) -> AIService:
    """
    获取当前用户的AI服务实例
    从数据库读取用户设置并创建对应的AI服务

    Args:
        user_id: 用户ID
        db: 数据库会话

    Returns:
        AIService: 使用用户配置创建的AI服务实例
    """
    result = await db.execute(
        select(Settings).where(Settings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # 如果用户没有设置，从环境变量读取并保存
        env_defaults = _read_env_defaults()
        settings = Settings(
            user_id=user_id,
            **env_defaults
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        logger.info(f"用户 {user_id} 首次使用AI服务，已从环境变量同步设置到数据库")

    # 使用用户设置创建AI服务实例
    return create_user_ai_service(
        api_provider=settings.api_provider,
        api_key=settings.api_key,
        api_base_url=settings.api_base_url or "",
        model_name=settings.llm_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens
    )


def get_extractor(ai_service: Optional[AIService] = None) -> EntityExtractor:
    """获取实体提取器

    Args:
        ai_service: AI服务实例（传入则使用AI提取，否则使用规则匹配）
    """
    return EntityExtractor(ai_service=ai_service)


def get_detector(ai_service: Optional[AIService] = None) -> ConflictDetector:
    """获取矛盾检测器

    Args:
        ai_service: AI服务实例（传入则使用AI辅助判断）
    """
    return ConflictDetector(ai_service=ai_service)


@router.post("/extract/{project_id}", summary="提取项目中的所有实体设定")
async def extract_entities(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = Query("incremental", description="提取模式: incremental(增量)/full(全量)"),
    use_ai: bool = Query(False, description="是否使用AI提取（使用用户配置的AI设置）")
) -> Dict[str, Any]:
    """
    从项目的所有章节中提取实体设定快照

    Args:
        project_id: 项目ID
        mode: 提取模式 - incremental(只处理新章节) / full(清空后全量提取)
        use_ai: 是否使用AI提取（将使用用户在设置中配置的AI服务）
    """
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="需要登录")

    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 全量模式：先清空已有数据
    if mode == "full":
        # 必须先删除关联的矛盾记录，否则会触发外键约束错误
        await db.execute(
            Conflict.__table__.delete().where(Conflict.project_id == project_id)
        )
        logger.info(f"全量模式: 已自动清理项目 {project_id} 的关联矛盾记录")
        
        await db.execute(
            EntitySnapshot.__table__.delete().where(EntitySnapshot.project_id == project_id)
        )
        await db.commit()
        logger.info(f"全量模式: 已清空项目 {project_id} 的实体快照")

    # 获取项目所有章节
    result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number)
    )
    all_chapters = result.scalars().all()

    if not all_chapters:
        return {"message": "项目没有章节", "extracted": 0, "errors": [], "skipped": 0}

    # 增量模式：只处理未提取过的章节
    chapters_to_process = all_chapters
    skipped_count = 0

    if mode == "incremental":
        # 查询已提取过的章节ID
        extracted_result = await db.execute(
            select(EntitySnapshot.source_chapter_id).where(
                EntitySnapshot.project_id == project_id
            ).distinct()
        )
        extracted_chapter_ids = set(row[0] for row in extracted_result.all() if row[0])

        # 过滤出未提取的章节
        chapters_to_process = [ch for ch in all_chapters if ch.id not in extracted_chapter_ids]
        skipped_count = len(all_chapters) - len(chapters_to_process)

        if not chapters_to_process:
            return {
                "message": "所有章节都已提取过，无需重复提取",
                "extracted": 0,
                "errors": [],
                "skipped": skipped_count,
                "mode": mode
            }

    # 获取用户的AI服务（如果需要使用AI）
    ai_service = None
    ai_provider = None
    ai_model = None
    if use_ai:
        try:
            ai_service = await get_user_ai_service(user_id, db)
            ai_provider = ai_service.api_provider
            ai_model = ai_service.default_model
            logger.info(f"使用用户AI设置: provider={ai_provider}, model={ai_model}")
        except Exception as e:
            logger.error(f"获取用户AI设置失败: {str(e)}")
            raise HTTPException(status_code=400, detail=f"获取AI设置失败: {str(e)}")

    # 批量提取
    extractor = get_extractor(ai_service=ai_service)
    total_extracted, error_chapters = await extractor.batch_extract(
        chapters=chapters_to_process,
        db=db,
        ai_provider=ai_provider,
        ai_model=ai_model
    )

    logger.info(f"实体提取完成: project_id={project_id}, mode={mode}, extracted={total_extracted}, skipped={skipped_count}")

    return {
        "message": f"提取完成（{mode}模式）",
        "extracted": total_extracted,
        "errors": error_chapters,
        "skipped": skipped_count,
        "processed": len(chapters_to_process),
        "mode": mode
    }


@router.post("/detect/{project_id}", summary="检测项目中的所有矛盾")
async def detect_conflicts(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    clear_existing: bool = Query(False, description="是否清空已有矛盾重新检测"),
    use_ai: bool = Query(False, description="是否使用AI辅助判断矛盾（使用用户配置的AI设置）"),
    auto_save: bool = Query(True, description="是否自动保存检测结果")
) -> Dict[str, Any]:
    """
    检测项目中的设定矛盾

    Args:
        project_id: 项目ID
        clear_existing: 是否清空已有矛盾记录后重新检测
        use_ai: 是否使用AI辅助判断（将使用用户在设置中配置的AI服务）
        auto_save: 是否自动保存检测结果到数据库
    """
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="需要登录")

    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 清空已有矛盾
    if clear_existing:
        await db.execute(
            Conflict.__table__.delete().where(Conflict.project_id == project_id)
        )
        await db.commit()
        logger.info(f"已清空项目 {project_id} 的矛盾记录")

    # 获取用户的AI服务（如果需要使用AI）
    ai_service = None
    if use_ai:
        try:
            ai_service = await get_user_ai_service(user_id, db)
            logger.info(f"矛盾检测使用用户AI设置: provider={ai_service.api_provider}, model={ai_service.default_model}")
        except Exception as e:
            logger.error(f"获取用户AI设置失败: {str(e)}")
            raise HTTPException(status_code=400, detail=f"获取AI设置失败: {str(e)}")

    # 检测矛盾
    detector = get_detector(ai_service=ai_service)
    conflicts = await detector.detect_all(project_id, db)

    if not conflicts:
        return {"message": "未检测到矛盾", "count": 0}

    # 自动保存
    if auto_save:
        saved_count, error_ids = await detector.save_conflicts(conflicts, db)
    else:
        saved_count = 0
        error_ids = []

    # 构建响应
    conflict_details = []
    for conflict in conflicts:
        conflict_details.append({
            "entityId": conflict.entity_id,
            "entityName": conflict.entity_name,
            "property": conflict.property_display,
            "valueA": conflict.snapshot_a_value[:100],
            "valueB": conflict.snapshot_b_value[:100],
            "severity": conflict.severity,
            "description": conflict.description,
            "aiSuggestion": conflict.ai_suggestion
        })

    logger.info(f"矛盾检测完成: project_id={project_id}, found={len(conflicts)}, saved={saved_count}")

    return {
        "message": f"检测到 {len(conflicts)} 个矛盾",
        "count": len(conflicts),
        "saved": saved_count,
        "errors": error_ids,
        "conflicts": conflict_details
    }


@router.get("/{project_id}", summary="获取项目矛盾列表", response_model=ConflictListResponse)
async def get_conflicts(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    severity: Optional[str] = Query(None, description="严重程度筛选: critical/warning/info"),
    status: Optional[str] = Query(None, description="状态筛选: detected/verified/resolved/ignored"),
    entity_id: Optional[str] = Query(None, description="实体ID筛选")
) -> Dict[str, Any]:
    """获取项目的矛盾列表"""
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 查询矛盾
    detector = get_detector()
    if entity_id:
        conflicts = await detector.get_conflicts_by_entity(project_id, entity_id, db)
    else:
        conflicts = await detector.get_conflicts_by_project(project_id, db, severity, status)

    # 构建响应
    items = []
    for conflict in conflicts:
        items.append(ConflictResponse(
            id=conflict.id,
            entityId=conflict.entity_id,
            entityName=conflict.entity_name,
            property=conflict.property_display,
            valueA=conflict.snapshot_a_value[:100],
            valueB=conflict.snapshot_b_value[:100],
            severity=conflict.severity,
            status=conflict.status,
            description=conflict.description,
            aiSuggestion=conflict.ai_suggestion
        ))

    return {
        "total": len(items),
        "items": items
    }


@router.get("/detail/{conflict_id}", summary="获取矛盾详情", response_model=ConflictDetailResponse)
async def get_conflict_detail(
    conflict_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取矛盾详情"""
    # 验证权限（通过冲突所属项目）
    user_id = getattr(request.state, 'user_id', None)

    conflict = await db.get(Conflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="矛盾不存在")

    project = await db.get(Project, conflict.project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问该项目")

    # 获取快照详情
    snapshot_a = await db.get(EntitySnapshot, conflict.snapshot_a_id)
    snapshot_b = await db.get(EntitySnapshot, conflict.snapshot_b_id)

    return {
        "id": conflict.id,
        "entity": {
            "id": conflict.entity_id,
            "name": conflict.entity_name,
            "type": conflict.entity_type
        },
        "property": {
            "name": conflict.property_name,
            "displayName": conflict.property_display
        },
        "snapshotA": {
            "value": conflict.snapshot_a_value,
            "sourceChapterId": conflict.snapshot_a_source,
            "quote": snapshot_a.source_quote if snapshot_a else "",
            "context": snapshot_a.source_context if snapshot_a else ""
        },
        "snapshotB": {
            "value": conflict.snapshot_b_value,
            "sourceChapterId": conflict.snapshot_b_source,
            "quote": snapshot_b.source_quote if snapshot_b else "",
            "context": snapshot_b.source_context if snapshot_b else ""
        },
        "conflict": {
            "type": conflict.conflict_type,
            "severity": conflict.severity,
            "description": conflict.description,
            "detectedAt": conflict.created_at.isoformat() if conflict.created_at else None,
            "status": conflict.status
        },
        "aiSuggestion": conflict.ai_suggestion
    }


@router.post("/resolve/{conflict_id}", summary="解决矛盾")
async def resolve_conflict(
    conflict_id: str,
    request: Request,
    resolve_data: ConflictResolveRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, bool]:
    """解决矛盾"""
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)

    conflict = await db.get(Conflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="矛盾不存在")

    project = await db.get(Project, conflict.project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权操作")

    # 解决矛盾
    detector = get_detector()
    success = await detector.resolve_conflict(
        conflict_id=conflict_id,
        resolution=resolve_data.resolution,
        resolved_by=user_id,
        db=db
    )

    return {"success": success}


@router.post("/ignore/{conflict_id}", summary="忽略矛盾")
async def ignore_conflict(
    conflict_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, bool]:
    """忽略矛盾（标记为不是真正的矛盾）"""
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)

    conflict = await db.get(Conflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="矛盾不存在")

    project = await db.get(Project, conflict.project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权操作")

    # 忽略矛盾
    detector = get_detector()
    success = await detector.ignore_conflict(conflict_id, db)

    return {"success": success}


@router.get("/entity/{project_id}/{entity_id}", summary="获取实体的所有设定")
async def get_entity_snapshots(
    project_id: str,
    entity_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取某个实体的所有设定快照"""
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 查询该实体的所有快照
    result = await db.execute(
        select(EntitySnapshot).where(
            EntitySnapshot.project_id == project_id,
            EntitySnapshot.entity_id == entity_id
        ).order_by(EntitySnapshot.property_name, EntitySnapshot.created_at)
    )
    snapshots = result.scalars().all()

    # 按属性分组
    property_groups = {}
    for snapshot in snapshots:
        if snapshot.property_name not in property_groups:
            property_groups[snapshot.property_name] = []

        property_groups[snapshot.property_name].append({
            "id": snapshot.id,
            "value": snapshot.property_value,
            "propertyType": snapshot.property_type,
            "sourceChapterId": snapshot.source_chapter_id,
            "quote": snapshot.source_quote,
            "confidence": snapshot.confidence,
            "createdAt": snapshot.created_at.isoformat() if snapshot.created_at else None
        })

    # 检测每个属性是否有矛盾
    detector = get_detector()
    conflicts = await detector.get_conflicts_by_entity(project_id, entity_id, db)
    conflict_map = {
        f"{conflict.property_name}": conflict.status
        for conflict in conflicts
    }

    result = {
        "entityId": entity_id,
        "entityName": snapshots[0].entity_name if snapshots else "",
        "entityType": snapshots[0].entity_type if snapshots else "",
        "properties": [
            {
                "propertyName": prop_name,
                "displayName": detector._get_property_display(prop_name),
                "snapshots": prop_snapshots,
                "hasConflict": prop_name in conflict_map,
                "conflictStatus": conflict_map.get(prop_name, "none")
            }
            for prop_name, prop_snapshots in property_groups.items()
        ]
    }

    return result
