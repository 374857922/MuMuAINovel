"""
智能改写服务 - AI辅助文风优化
"""
from typing import AsyncGenerator, Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.ai_service import AIService
from app.models.ai_vocabulary import RewriteRecord
from app.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# 改写 Prompt 模板
# ============================================================

PROMPT_REPLACE = """请将以下句子中的「{word}」替换为更自然的表达。

要求：
1. 保持原意不变
2. 符合上下文语境
3. 避免使用其他AI常用词汇（如：不禁、缓缓、微微、心中涌起等）
4. 让表达更口语化、更有"人味"

原句：{sentence}

上下文（供参考）：
{context}

建议替换词：{alternatives}

请直接输出替换后的完整句子，不要解释。"""


PROMPT_REWRITE = """请改写以下句子，使其更自然、更有"人味"，消除AI腔调。

原句：{sentence}

问题分析：{issue_description}

改写要求：
1. 保持原意不变
2. 避免使用以下AI常用词汇：{banned_words}
3. 可以适当调整句式和用词
4. 让情感表达更含蓄、更有层次感
5. 如果是情感描写，尝试用具体行为展示，而非直接描述心理

上下文（供参考）：
{context}

请直接输出改写后的句子，不要解释。"""


PROMPT_RESTRUCTURE = """请改写以下段落，消除AI痕迹，使其更有个人风格和文学性。

原文：
{paragraph}

检测到的问题：
{issues}

改写原则：
1. 保持核心情节和信息不变
2. 打破过于工整的结构，增加变化
3. 句子长短要有明显变化，形成节奏感
4. 可以加入口语化表达或更生动的描写
5. 情感表达要有留白，不要过于直白
6. 减少连接词（首先、其次、然后等）的使用

禁止使用的表达：
{banned_expressions}

{style_reference}

请直接输出改写后的段落，不要解释。"""


# 常见的AI腔调词汇黑名单
AI_BANNED_WORDS = [
    "不禁", "不由得", "不由自主", "缓缓", "微微", "淡淡的", "轻轻地", "静静地",
    "默默地", "深深地", "心中涌起", "心头一紧", "心中一暖", "眼眶泛红", "嘴角上扬",
    "就在这时", "话音刚落", "与此同时", "值得注意的是", "需要指出的是",
    "综上所述", "由此可见", "不难发现", "显而易见"
]


# ============================================================
# 改写服务
# ============================================================

async def rewrite_text_stream(
    ai_service: AIService,
    text: str,
    rewrite_type: str,
    issue: Optional[Dict] = None,
    context: str = "",
    style_sample: str = "",
    banned_words: Optional[List[str]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    流式改写文本

    Args:
        ai_service: AI服务实例
        text: 待改写文本
        rewrite_type: 改写类型 (replace/rewrite/restructure)
        issue: 触发改写的问题（包含word、alternatives、description等）
        context: 上下文
        style_sample: 参考风格样本
        banned_words: 额外禁止使用的词汇
        provider: AI提供商
        model: AI模型

    Yields:
        改写后的文本片段
    """
    # 合并禁用词列表
    all_banned = AI_BANNED_WORDS.copy()
    if banned_words:
        all_banned.extend(banned_words)

    # 构建prompt
    if rewrite_type == "replace" and issue:
        prompt = PROMPT_REPLACE.format(
            word=issue.get("word", ""),
            sentence=text,
            context=context or "无",
            alternatives=", ".join(issue.get("alternatives", ["更自然的表达"]))
        )
    elif rewrite_type == "rewrite" and issue:
        prompt = PROMPT_REWRITE.format(
            sentence=text,
            issue_description=issue.get("description", "存在AI腔调"),
            banned_words="、".join(all_banned[:20]),  # 限制长度
            context=context or "无"
        )
    elif rewrite_type == "restructure":
        # 整段改写
        issues_text = ""
        if issue:
            if isinstance(issue, list):
                issues_text = "\n".join([f"- {i.get('word', '')}：{i.get('description', '')}" for i in issue[:5]])
            else:
                issues_text = f"- {issue.get('word', '')}：{issue.get('description', '')}"

        style_ref = ""
        if style_sample:
            style_ref = f"\n参考风格：\n{style_sample}\n"

        prompt = PROMPT_RESTRUCTURE.format(
            paragraph=text,
            issues=issues_text or "句式单一、表达套路化",
            banned_expressions="、".join(all_banned[:15]),
            style_reference=style_ref
        )
    else:
        # 默认使用通用改写
        prompt = PROMPT_REWRITE.format(
            sentence=text,
            issue_description="存在AI腔调痕迹",
            banned_words="、".join(all_banned[:20]),
            context=context or "无"
        )

    # 系统提示词
    system_prompt = """你是一位经验丰富的文字编辑，专门帮助作者优化文字表达。
你的任务是消除文本中的"AI腔调"，让文字更自然、更有人味。

AI腔调的特征：
- 使用过于书面化的词汇（如：值得注意的是、综上所述）
- 频繁使用程度副词（如：缓缓、微微、淡淡的）
- 情感描写过于直白（如：心中涌起一股暖流）
- 句式过于工整，缺乏变化
- 连接词使用过多（如：首先、其次、最后）

你的改写应该：
- 保持原意，不改变核心内容
- 用更口语化、更生动的表达替代套话
- 增加句式变化，形成自然的节奏
- 情感表达含蓄，用行为和细节展示而非直接描述

直接输出改写结果，不要解释或添加其他内容。"""

    logger.info(f"开始改写: type={rewrite_type}, text_len={len(text)}")

    try:
        async for chunk in ai_service.generate_text_stream(
            prompt=prompt,
            provider=provider,
            model=model,
            temperature=0.7,
            max_tokens=len(text) * 3,  # 预留足够空间
            system_prompt=system_prompt
        ):
            yield chunk
    except Exception as e:
        logger.error(f"改写失败: {e}")
        raise


async def save_rewrite_record(
    db: AsyncSession,
    project_id: str,
    chapter_id: Optional[str],
    original_text: str,
    rewritten_text: str,
    rewrite_type: str,
    trigger_type: str,
    trigger_issue: Optional[Dict] = None,
    ai_model: Optional[str] = None
) -> RewriteRecord:
    """
    保存改写记录

    Args:
        db: 数据库会话
        project_id: 项目ID
        chapter_id: 章节ID（可选）
        original_text: 原始文本
        rewritten_text: 改写后文本
        rewrite_type: 改写类型
        trigger_type: 触发类型
        trigger_issue: 触发的问题
        ai_model: 使用的AI模型

    Returns:
        保存的记录
    """
    record = RewriteRecord(
        project_id=project_id,
        chapter_id=chapter_id,
        original_text=original_text,
        rewritten_text=rewritten_text,
        rewrite_type=rewrite_type,
        trigger_type=trigger_type,
        trigger_issue=trigger_issue,
        ai_model=ai_model,
        status="pending"
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    logger.info(f"保存改写记录: id={record.id}, type={rewrite_type}")
    return record


async def update_rewrite_status(
    db: AsyncSession,
    record_id: str,
    status: str
) -> Optional[RewriteRecord]:
    """
    更新改写记录状态

    Args:
        db: 数据库会话
        record_id: 记录ID
        status: 新状态 (accepted/rejected)

    Returns:
        更新后的记录
    """
    result = await db.execute(
        select(RewriteRecord).where(RewriteRecord.id == record_id)
    )
    record = result.scalars().first()

    if record:
        record.status = status
        if status == "accepted":
            from datetime import datetime
            record.accepted_at = datetime.now().isoformat()
        await db.commit()
        await db.refresh(record)
        logger.info(f"更新改写状态: id={record_id}, status={status}")

    return record


async def get_rewrite_history(
    db: AsyncSession,
    project_id: str,
    chapter_id: Optional[str] = None,
    limit: int = 20
) -> List[Dict]:
    """
    获取改写历史

    Args:
        db: 数据库会话
        project_id: 项目ID
        chapter_id: 章节ID（可选）
        limit: 返回数量限制

    Returns:
        改写记录列表
    """
    # 先构建基础查询条件
    conditions = [RewriteRecord.project_id == project_id]
    if chapter_id:
        conditions.append(RewriteRecord.chapter_id == chapter_id)

    # 按正确顺序构建查询：where → order_by → limit
    query = (
        select(RewriteRecord)
        .where(*conditions)
        .order_by(RewriteRecord.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    records = result.scalars().all()

    return [r.to_dict() for r in records]
