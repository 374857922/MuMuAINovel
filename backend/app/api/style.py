"""
文风检测API - AI腔调检测和词汇替换
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any, AsyncGenerator
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.ai_vocabulary import AIVocabulary, ChapterToneAnalysis, RewriteRecord
from app.models.chapter import Chapter
from app.api.chapters import verify_project_access
from app.api.settings import get_user_ai_service
from app.services.ai_service import AIService
from app.services.style_analyzer import (
    analyze_chapter_tone,
    get_vocabulary_list,
    init_ai_vocabulary,
    batch_replace_words,
    get_chapter_analysis
)
from app.services.pattern_analyzer import (
    analyze_project_patterns,
    get_pattern_analysis
)
from app.services.style_rewriter import (
    rewrite_text_stream,
    save_rewrite_record,
    update_rewrite_status,
    get_rewrite_history
)
from app.utils.sse_response import SSEResponse, create_sse_response
from app.logger import get_logger

router = APIRouter(prefix="/style", tags=["文风检测"])
logger = get_logger(__name__)


# ============================================================
# Pydantic Schemas
# ============================================================

class ToneAnalyzeRequest(BaseModel):
    """文风检测请求"""
    text: Optional[str] = Field(None, description="待检测文本（与chapter_id二选一）")
    chapter_id: Optional[str] = Field(None, description="章节ID（与text二选一）")
    project_id: Optional[str] = Field(None, description="项目ID（使用chapter_id时可选）")


class IssuePosition(BaseModel):
    """问题位置"""
    start: int
    end: int
    context: str


class ToneIssue(BaseModel):
    """检测到的问题"""
    type: str = Field(..., description="问题类型: vocabulary/sentence_uniformity/connector_overuse")
    severity: str = Field(..., description="严重程度: high/medium/low")
    word: Optional[str] = Field(None, description="问题词汇")
    category: Optional[str] = Field(None, description="词汇分类")
    count: Optional[int] = Field(None, description="出现次数")
    positions: Optional[List[dict]] = Field(None, description="位置列表")
    alternatives: Optional[List[str]] = Field(None, description="替换建议")
    description: Optional[str] = Field(None, description="问题说明")
    message: Optional[str] = Field(None, description="提示信息")
    suggestion: Optional[str] = Field(None, description="改进建议")


class ToneStats(BaseModel):
    """统计信息"""
    word_count: int
    sentence_count: int
    avg_sentence_length: float
    sentence_length_std: float


class ToneAnalyzeResponse(BaseModel):
    """文风检测响应"""
    score: int = Field(..., description="自然度评分 0-100")
    level: str = Field(..., description="评级: 自然/一般/明显/严重")
    issue_count: int = Field(..., description="问题数量")
    issues: List[ToneIssue] = Field(..., description="问题列表")
    stats: ToneStats = Field(..., description="统计信息")
    summary: str = Field(..., description="结果摘要")


class VocabularyItem(BaseModel):
    """词汇库条目"""
    id: str
    word: str
    category: str
    severity: str
    alternatives: List[str]
    description: Optional[str]
    usage_count: int
    is_system: int


class VocabularyListResponse(BaseModel):
    """词汇库列表响应"""
    total: int
    items: List[VocabularyItem]


class VocabularyCreateRequest(BaseModel):
    """添加自定义词汇"""
    word: str = Field(..., max_length=100, description="词汇")
    category: str = Field("warning", description="分类")
    severity: str = Field("medium", description="严重程度")
    alternatives: List[str] = Field(default=[], description="替换建议")
    description: Optional[str] = Field(None, description="说明")


class ReplaceItem(BaseModel):
    """替换项"""
    original: str = Field(..., description="原词")
    replacement: str = Field(..., description="替换为")
    position: Optional[dict] = Field(None, description="指定位置（可选）")


class ReplaceRequest(BaseModel):
    """批量替换请求"""
    chapter_id: str = Field(..., description="章节ID")
    replacements: List[ReplaceItem] = Field(..., description="替换列表")


class ReplaceResponse(BaseModel):
    """批量替换响应"""
    success: bool
    replaced_count: int
    new_content: str


# ============================================================
# API Endpoints
# ============================================================

@router.post("/analyze-tone", response_model=ToneAnalyzeResponse, summary="分析文风/AI腔调")
async def analyze_tone(
    request_data: ToneAnalyzeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    分析文本的AI腔调

    可以传入text直接分析，或传入chapter_id分析指定章节
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    text = request_data.text
    chapter_id = request_data.chapter_id
    project_id = request_data.project_id

    # 验证参数
    if not text and not chapter_id:
        raise HTTPException(status_code=400, detail="请提供text或chapter_id")

    # 如果提供了chapter_id，获取章节内容
    if chapter_id:
        result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
        chapter = result.scalars().first()

        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在")

        # 验证项目权限
        await verify_project_access(chapter.project_id, user_id, db)

        text = chapter.content
        project_id = chapter.project_id

        if not text:
            raise HTTPException(status_code=400, detail="章节内容为空")

    # 如果提供了project_id但没有chapter_id，验证项目权限
    if project_id and not chapter_id:
        await verify_project_access(project_id, user_id, db)

    # 执行检测
    try:
        result = await analyze_chapter_tone(
            db=db,
            text=text,
            project_id=project_id,
            chapter_id=chapter_id
        )

        logger.info(f"文风检测完成: score={result['score']}, issues={result['issue_count']}")
        return result

    except Exception as e:
        logger.error(f"文风检测失败: {e}")
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")


@router.get("/analysis/{chapter_id}", summary="获取章节的检测结果")
async def get_analysis(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """获取已保存的章节检测结果"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 获取章节信息
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()

    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 验证权限
    await verify_project_access(chapter.project_id, user_id, db)

    # 获取检测结果
    analysis = await get_chapter_analysis(db, chapter_id)

    if not analysis:
        return {"message": "该章节尚未进行文风检测", "has_analysis": False}

    return {"has_analysis": True, "analysis": analysis}


@router.get("/vocabulary", response_model=VocabularyListResponse, summary="获取AI腔调词汇库")
async def get_vocabulary(
    request: Request,
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None, description="筛选分类: critical/warning/emotional/scene/transition")
):
    """获取AI腔调词汇库列表"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 确保词汇库已初始化
    await init_ai_vocabulary(db)

    items = await get_vocabulary_list(db, category)

    return VocabularyListResponse(total=len(items), items=items)


@router.post("/vocabulary", summary="添加自定义词汇")
async def add_vocabulary(
    vocab_data: VocabularyCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """添加自定义AI腔调词汇"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 检查词汇是否已存在
    result = await db.execute(
        select(AIVocabulary).where(AIVocabulary.word == vocab_data.word)
    )
    existing = result.scalars().first()

    if existing:
        raise HTTPException(status_code=400, detail="该词汇已存在")

    # 创建新词汇
    vocab = AIVocabulary(
        word=vocab_data.word,
        category=vocab_data.category,
        severity=vocab_data.severity,
        alternatives=vocab_data.alternatives,
        description=vocab_data.description,
        is_system=0  # 用户自定义
    )
    db.add(vocab)
    await db.commit()
    await db.refresh(vocab)

    logger.info(f"添加自定义词汇: {vocab.word}")
    return vocab.to_dict()


@router.delete("/vocabulary/{vocab_id}", summary="删除自定义词汇")
async def delete_vocabulary(
    vocab_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """删除自定义词汇（系统预置词汇不可删除）"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    result = await db.execute(select(AIVocabulary).where(AIVocabulary.id == vocab_id))
    vocab = result.scalars().first()

    if not vocab:
        raise HTTPException(status_code=404, detail="词汇不存在")

    if vocab.is_system == 1:
        raise HTTPException(status_code=400, detail="系统预置词汇不可删除")

    await db.delete(vocab)
    await db.commit()

    logger.info(f"删除自定义词汇: {vocab.word}")
    return {"message": "删除成功"}


@router.post("/replace", response_model=ReplaceResponse, summary="批量替换词汇")
async def replace_words(
    replace_data: ReplaceRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """批量替换章节中的词汇"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 获取章节
    result = await db.execute(select(Chapter).where(Chapter.id == replace_data.chapter_id))
    chapter = result.scalars().first()

    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 验证权限
    await verify_project_access(chapter.project_id, user_id, db)

    if not chapter.content:
        raise HTTPException(status_code=400, detail="章节内容为空")

    # 执行替换
    replacements = [r.model_dump() for r in replace_data.replacements]
    new_content = await batch_replace_words(chapter.content, replacements)

    # 计算替换数量
    replaced_count = sum(
        chapter.content.count(r["original"]) if "position" not in r else 1
        for r in replacements
    )

    # 更新章节内容
    chapter.content = new_content
    await db.commit()

    logger.info(f"词汇替换完成: chapter_id={chapter.id}, replaced={replaced_count}")

    return ReplaceResponse(
        success=True,
        replaced_count=replaced_count,
        new_content=new_content
    )


@router.post("/init-vocabulary", summary="初始化词汇库")
async def initialize_vocabulary(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """手动初始化AI腔调词汇库"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    count = await init_ai_vocabulary(db)

    return {"message": f"词汇库初始化完成，共{count}条词汇"}


# ============================================================
# 跨章节套路化分析 API
# ============================================================

class PatternExample(BaseModel):
    """模式示例"""
    chapter: int
    text: str


class OpeningAnalysis(BaseModel):
    """开场分析"""
    total_chapters: int
    categories: dict
    examples: dict
    dominant_type: str
    dominant_count: int
    dominant_ratio: float
    is_monotonous: bool
    suggestion: str


class EmotionData(BaseModel):
    """情感数据"""
    expressions: List[tuple]
    total_count: int
    unique_count: int
    concentration: float
    top_expression: Optional[str]
    top_count: int


class EmotionDiversity(BaseModel):
    """情感多样性"""
    emotions: dict
    diversity_score: int
    total_expressions: int
    total_unique: int
    most_concentrated_emotion: Optional[str]
    suggestion: str


class PatternItem(BaseModel):
    """模式条目"""
    template: str
    count: int
    examples: List[str]
    chapters: List[int]
    is_opening_pattern: bool
    is_ending_pattern: bool


class PatternAnalysisResponse(BaseModel):
    """套路化分析响应"""
    model_config = {"extra": "ignore"}  # 忽略额外字段
    status: str
    score: Optional[int] = None
    level: Optional[str] = None
    chapters_analyzed: Optional[int] = None
    patterns_found: Optional[int] = None
    top_patterns: Optional[List[PatternItem]] = None
    opening_analysis: Optional[dict] = None
    emotion_diversity: Optional[dict] = None
    suggestions: Optional[List[str]] = None
    message: Optional[str] = None
    current_chapters: Optional[int] = None


@router.post("/analyze-patterns/{project_id}", response_model=PatternAnalysisResponse, summary="分析项目套路化程度")
async def analyze_patterns(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    min_chapters: int = Query(5, description="最少章节数要求")
):
    """
    跨章节套路化分析

    分析项目所有章节，检测：
    - 重复句式模式
    - 开场方式单一性
    - 情感表达词汇多样性

    需要至少5个章节才能进行分析
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 验证项目权限
    await verify_project_access(project_id, user_id, db)

    try:
        result = await analyze_project_patterns(db, project_id, min_chapters)
        logger.info(f"套路化分析完成: project_id={project_id}, status={result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"套路化分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.get("/patterns/{project_id}", response_model=PatternAnalysisResponse, summary="获取套路化分析结果")
async def get_patterns(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """获取已保存的套路化分析结果"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 验证项目权限
    await verify_project_access(project_id, user_id, db)

    result = await get_pattern_analysis(db, project_id)

    if not result:
        return PatternAnalysisResponse(
            status="no_analysis",
            message="该项目尚未进行套路化分析"
        )

    return PatternAnalysisResponse(status="success", **result)


# ============================================================
# 智能改写 API
# ============================================================

class RewriteRequest(BaseModel):
    """改写请求"""
    text: str = Field(..., min_length=1, description="待改写文本")
    chapter_id: Optional[str] = Field(None, description="章节ID（可选）")
    project_id: Optional[str] = Field(None, description="项目ID（可选）")
    rewrite_type: str = Field("rewrite", description="改写类型: replace/rewrite/restructure")
    issue: Optional[Dict[str, Any]] = Field(None, description="触发改写的问题")
    context: str = Field("", description="上下文")
    style_sample: str = Field("", description="参考风格样本")
    banned_words: Optional[List[str]] = Field(None, description="额外禁止词汇")


class RewriteHistoryItem(BaseModel):
    """改写历史条目"""
    id: str
    project_id: str
    chapter_id: Optional[str]
    original_text: str
    rewritten_text: str
    rewrite_type: str
    trigger_type: str
    status: str
    created_at: str


class RewriteHistoryResponse(BaseModel):
    """改写历史响应"""
    total: int
    items: List[RewriteHistoryItem]


class RewriteStatusRequest(BaseModel):
    """更新改写状态请求"""
    status: str = Field(..., description="状态: accepted/rejected")


@router.post("/rewrite-stream", summary="流式改写文本")
async def rewrite_stream(
    rewrite_data: RewriteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    流式改写文本，消除AI腔调

    改写类型：
    - replace: 词汇替换（保留句式，只替换特定词）
    - rewrite: 句子改写（保持原意，调整表达）
    - restructure: 段落重构（打散重组，提升多样性）
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 如果提供了project_id，验证权限
    if rewrite_data.project_id:
        await verify_project_access(rewrite_data.project_id, user_id, db)

    # 如果提供了chapter_id，获取chapter并验证权限
    if rewrite_data.chapter_id:
        result = await db.execute(select(Chapter).where(Chapter.id == rewrite_data.chapter_id))
        chapter = result.scalars().first()
        if chapter:
            await verify_project_access(chapter.project_id, user_id, db)
            if not rewrite_data.project_id:
                rewrite_data.project_id = chapter.project_id

    async def generate():
        """流式生成改写结果"""
        accumulated_text = ""
        try:
            yield await SSEResponse.send_progress("开始改写...", 0)

            async for chunk in rewrite_text_stream(
                ai_service=user_ai_service,
                text=rewrite_data.text,
                rewrite_type=rewrite_data.rewrite_type,
                issue=rewrite_data.issue,
                context=rewrite_data.context,
                style_sample=rewrite_data.style_sample,
                banned_words=rewrite_data.banned_words
            ):
                accumulated_text += chunk
                yield await SSEResponse.send_chunk(chunk)

            yield await SSEResponse.send_progress("改写完成", 100, "success")

            # 保存改写记录（如果提供了project_id）
            record_id = None
            if rewrite_data.project_id and accumulated_text:
                record = await save_rewrite_record(
                    db=db,
                    project_id=rewrite_data.project_id,
                    chapter_id=rewrite_data.chapter_id,
                    original_text=rewrite_data.text,
                    rewritten_text=accumulated_text,
                    rewrite_type=rewrite_data.rewrite_type,
                    trigger_type="manual",
                    trigger_issue=rewrite_data.issue,
                    ai_model=user_ai_service.default_model
                )
                record_id = record.id

            # 发送最终结果
            yield await SSEResponse.send_result({
                "original": rewrite_data.text,
                "rewritten": accumulated_text,
                "record_id": record_id
            })

            yield await SSEResponse.send_done()

        except Exception as e:
            logger.error(f"改写失败: {e}")
            yield await SSEResponse.send_error(f"改写失败: {str(e)}")

    return create_sse_response(generate())


@router.get("/rewrite-history/{project_id}", response_model=RewriteHistoryResponse, summary="获取改写历史")
async def get_history(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    chapter_id: Optional[str] = Query(None, description="筛选章节ID"),
    limit: int = Query(20, ge=1, le=100, description="返回数量")
):
    """获取项目的改写历史记录"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 验证项目权限
    await verify_project_access(project_id, user_id, db)

    records = await get_rewrite_history(db, project_id, chapter_id, limit)

    return RewriteHistoryResponse(
        total=len(records),
        items=[RewriteHistoryItem(**r) for r in records]
    )


@router.put("/rewrite-record/{record_id}/status", summary="更新改写记录状态")
async def update_record_status(
    record_id: str,
    status_data: RewriteStatusRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    更新改写记录状态

    用户可以接受或拒绝改写建议：
    - accepted: 采纳改写
    - rejected: 拒绝改写
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    if status_data.status not in ["accepted", "rejected"]:
        raise HTTPException(status_code=400, detail="状态必须为 accepted 或 rejected")

    # 获取记录并验证权限
    result = await db.execute(
        select(RewriteRecord).where(RewriteRecord.id == record_id)
    )
    record = result.scalars().first()

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 验证项目权限
    await verify_project_access(record.project_id, user_id, db)

    # 更新状态
    updated = await update_rewrite_status(db, record_id, status_data.status)

    if not updated:
        raise HTTPException(status_code=500, detail="更新失败")

    logger.info(f"改写记录状态更新: id={record_id}, status={status_data.status}")

    return {"message": "状态更新成功", "record": updated.to_dict()}


@router.post("/apply-rewrite/{record_id}", summary="应用改写到章节")
async def apply_rewrite(
    record_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    将改写结果应用到章节内容

    此操作会：
    1. 将章节中的原文替换为改写后的文本
    2. 将记录状态更新为 accepted
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 获取改写记录
    result = await db.execute(
        select(RewriteRecord).where(RewriteRecord.id == record_id)
    )
    record = result.scalars().first()

    if not record:
        raise HTTPException(status_code=404, detail="改写记录不存在")

    if not record.chapter_id:
        raise HTTPException(status_code=400, detail="该记录没有关联章节")

    # 获取章节
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == record.chapter_id)
    )
    chapter = chapter_result.scalars().first()

    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 验证权限
    await verify_project_access(chapter.project_id, user_id, db)

    # 执行替换
    if record.original_text not in chapter.content:
        raise HTTPException(status_code=400, detail="章节内容已变更，无法应用此改写")

    chapter.content = chapter.content.replace(record.original_text, record.rewritten_text, 1)

    # 更新记录状态
    await update_rewrite_status(db, record_id, "accepted")

    await db.commit()

    logger.info(f"应用改写: record_id={record_id}, chapter_id={chapter.id}")

    return {
        "message": "改写已应用",
        "chapter_id": chapter.id,
        "new_content_preview": chapter.content[:200] + "..." if len(chapter.content) > 200 else chapter.content
    }
