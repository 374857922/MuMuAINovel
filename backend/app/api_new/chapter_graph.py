"""章节关系图谱API - 思维链与可视化章节关系"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.models_new import ChapterLink, ThinkingChain
from app.models.chapter import Chapter
from app.models.project import Project
from app.services_new import LinkAnalyzer
from app.services.ai_service import AIService
from app.logger import get_logger

router = APIRouter(prefix="/chapter-graph", tags=["章节关系图谱"])
logger = get_logger(__name__)

# AI服务实例
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """获取AI服务单例"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


def get_analyzer(use_ai: bool = False) -> LinkAnalyzer:
    """获取链接分析器
    
    Args:
        use_ai: 是否使用AI（默认False，使用规则匹配更快）
    """
    if use_ai:
        return LinkAnalyzer(ai_service=get_ai_service())
    return LinkAnalyzer(ai_service=None)


@router.post("/analyze/{project_id}", summary="分析项目章节关系")
async def analyze_relationships(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ai_provider: Optional[str] = Query(None, description="AI提供商: openai/anthropic"),
    ai_model: Optional[str] = Query(None, description="AI模型")
) -> Dict[str, Any]:
    """
    分析项目中所有章节之间的关系

    Args:
        project_id: 项目ID
        ai_provider: AI提供商（可选）
        ai_model: AI模型（可选）
    """
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 分析关系（只有明确指定ai_provider时才用AI，否则用规则匹配更快）
    use_ai = ai_provider is not None
    analyzer = get_analyzer(use_ai=use_ai)
    links = await analyzer.analyze_all_relationships(
        project_id=project_id,
        db=db,
        ai_provider=ai_provider,
        ai_model=ai_model
    )

    if not links:
        return {"message": "未检测到章节关系", "count": 0, "saved": 0}

    # 保存关系
    saved_count, error_ids = await analyzer.save_links(links, db)

    # 统计关系类型
    link_types = {}
    for link in links:
        link_types[link.link_type] = link_types.get(link.link_type, 0) + 1

    logger.info(f"章节关系分析完成: project_id={project_id}, found={len(links)}, saved={saved_count}")

    return {
        "message": f"检测到 {len(links)} 个章节关系",
        "count": len(links),
        "saved": saved_count,
        "errors": error_ids,
        "summary": link_types
    }


@router.get("/links/{project_id}", summary="获取章节关系列表")
async def get_chapter_links(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    chapter_id: Optional[str] = Query(None, description="筛选特定章节的关系"),
    link_type: Optional[str] = Query(None, description="筛选特定类型"),
    limit: Optional[int] = Query(100, description="返回数量限制", ge=1, le=1000)
) -> Dict[str, Any]:
    """获取项目的章节关系列表"""
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 查询关系
    analyzer = get_analyzer()
    links = await analyzer.get_chapter_relationships(
        project_id=project_id,
        db=db,
        chapter_id=chapter_id,
        link_type=link_type
    )

    # 限制数量
    links = links[:limit]

    # 构建响应
    items = []
    for link in links:
        # 解析推理链
        reasoning_chain = {}
        if link.reasoning_chain:
            try:
                import json
                reasoning_chain = json.loads(link.reasoning_chain)
            except:
                pass

        items.append({
            "id": link.id,
            "fromChapter": {
                "id": link.from_chapter_id,
                "title": link.from_chapter_title
            },
            "toChapter": {
                "id": link.to_chapter_id,
                "title": link.to_chapter_title
            },
            "linkType": link.link_type,
            "linkTypeDisplay": link.link_type_display,
            "description": link.description,
            "fromElement": link.from_element,
            "toElement": link.to_element,
            "reasoningChain": reasoning_chain,
            "strength": link.strength,
            "importanceScore": link.importance_score,
            "confidence": link.confidence,
            "timeGap": link.time_gap
        })

    return {
        "total": len(items),
        "items": items
    }


@router.get("/graph/{project_id}", summary="获取图谱数据（可视化）")
async def get_graph_data(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    min_importance: Optional[float] = Query(0, description="最小重要性筛选", ge=0, le=100),
    exclude_types: Optional[str] = Query(None, description="排除的关系类型（逗号分隔）")
) -> Dict[str, Any]:
    """
    获取图谱数据（用于前端可视化）

    Returns:
        {
          "nodes": [{"id": "ch_1", "title": "第一章", "importance": 80}],
          "links": [{"source": "ch_1", "target": "ch_2", "type": "causality"}],
          "summary": {...}
        }
    """
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 获取图谱数据
    analyzer = get_analyzer()
    graph_data = await analyzer.build_graph_data(project_id, db)

    # 筛选
    if min_importance > 0:
        graph_data["nodes"] = [
            node for node in graph_data["nodes"]
            if node.get("importance", 0) >= min_importance
        ]
        graph_data["links"] = [
            link for link in graph_data["links"]
            if link.get("importance", 0) >= min_importance
        ]

    if exclude_types:
        exclude_list = exclude_types.split(",")
        graph_data["links"] = [
            link for link in graph_data["links"]
            if link["type"] not in exclude_list
        ]

    return graph_data


@router.get("/importance/{project_id}/{chapter_id}", summary="分析章节重要性")
async def get_chapter_importance(
    project_id: str,
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """分析单个章节在故事中的重要性"""
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 分析重要性
    analyzer = get_analyzer()
    analysis = await analyzer.analyze_chapter_importance(
        project_id=project_id,
        chapter_id=chapter_id,
        db=db
    )

    return analysis


@router.get("/thinking-chain/{chapter_id}", summary="获取章节思维链")
async def get_thinking_chain(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    chain_type: Optional[str] = Query(None, description="思维链类型: generation/analysis/detection")
) -> Dict[str, Any]:
    """获取章节的思维链记录"""
    # 验证权限（通过章节所属项目）
    user_id = getattr(request.state, 'user_id', None)

    chapter = await db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    project = await db.get(Project, chapter.project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")

    # 查询思维链
    query = select(ThinkingChain).where(ThinkingChain.chapter_id == chapter_id)
    if chain_type:
        query = query.where(ThinkingChain.chain_type == chain_type)
    query = query.order_by(ThinkingChain.created_at.desc())

    result = await db.execute(query)
    chains = result.scalars().all()

    items = []
    for chain in chains:
        reasoning_steps = []
        if chain.reasoning_steps:
            try:
                import json
                reasoning_steps = json.loads(chain.reasoning_steps)
            except:
                pass

        prompt_tokens = chain.prompt_tokens or 0
        completion_tokens = chain.completion_tokens or 0

        items.append({
            "id": chain.id,
            "type": chain.chain_type,
            "reasoningSteps": reasoning_steps,
            "conclusion": chain.conclusion,
            "aiModel": chain.ai_model,
            "tokenUsage": {
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "totalTokens": prompt_tokens + completion_tokens
            }
        })

    return {
        "total": len(items),
        "items": items
    }


@router.get("/path/{project_id}/{from_chapter_id}/{to_chapter_id}", summary="查找两个章节的关系路径")
async def find_relation_path(
    project_id: str,
    from_chapter_id: str,
    to_chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    max_hops: Optional[int] = Query(3, description="最大跳数", ge=1, le=5)
) -> Dict[str, Any]:
    """
    查找两个章节之间的关系路径

    例如：
    A章节 → X章节 → Y章节 → B章节
    """
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 获取所有关系
    analyzer = get_analyzer()
    links = await analyzer.get_chapter_relationships(project_id, db)

    # 构建图
    graph = {}
    for link in links:
        if link.from_chapter_id not in graph:
            graph[link.from_chapter_id] = []
        graph[link.from_chapter_id].append({
            "to": link.to_chapter_id,
            "link": link
        })

    # BFS查找路径
    visited = set()
    queue = [(from_chapter_id, [], 0)]  # (当前节点, 路径, 跳数)

    while queue:
        current, path, hops = queue.pop(0)

        if current == to_chapter_id:
            # 找到路径
            return {
                "found": True,
                "hops": hops,
                "path": path + [current]
            }

        if hops >= max_hops or current not in graph:
            continue

        if current in visited:
            continue
        visited.add(current)

        for edge in graph[current]:
            next_node = edge["to"]
            new_path = path + [current]
            queue.append((next_node, new_path, hops + 1))

    return {
        "found": False,
        "message": f"未找到从 {from_chapter_id} 到 {to_chapter_id} 的路径（最大{max_hops}跳）"
    }


@router.get("/stats/{project_id}", summary="获取图谱统计信息")
async def get_graph_stats(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取图谱的统计信息"""
    # 验证权限
    user_id = getattr(request.state, 'user_id', None)
    project = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not project.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 统计数据
    result = await db.execute(
        select(ChapterLink).where(ChapterLink.project_id == project_id)
    )
    links = result.scalars().all()

    # 按类型统计
    type_stats = {}
    for link in links:
        type_stats[link.link_type] = type_stats.get(link.link_type, 0) + 1

    # 按重要性统计
    high_importance = sum(1 for link in links if link.importance_score >= 80)
    medium_importance = sum(1 for link in links if 50 <= link.importance_score < 80)
    low_importance = sum(1 for link in links if link.importance_score < 50)

    # 获取章节数量
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id)
    )
    chapter_count = len(chapter_result.scalars().all())

    # 计算密度（连通度）
    density = len(links) / max(chapter_count, 1)

    return {
        "summary": {
            "totalLinks": len(links),
            "totalChapters": chapter_count,
            "density": round(density, 2),
            "coverage": round(min(1.0, density / 2), 2)  # 覆盖率（理想密度为2）
        },
        "byType": type_stats,
        "byImportance": {
            "high": high_importance,
            "medium": medium_importance,
            "low": low_importance
        },
        "mostConnected": [],  # TODO: 计算连接度最高的章节
        "keyChapters": []  # TODO: 计算关键章节
    }
