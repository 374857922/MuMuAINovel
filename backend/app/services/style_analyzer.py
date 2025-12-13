"""
文风检测服务 - AI腔调检测和套路化分析
"""
import re
import statistics
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_vocabulary import AIVocabulary, ChapterToneAnalysis
from app.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# 初始AI腔调词汇库数据
# ============================================================

INITIAL_VOCABULARY = [
    # === 高危词汇（几乎只有AI会用）===
    {"word": "值得注意的是", "category": "critical", "severity": "high",
     "alternatives": ["有意思的是", "说来也怪", "其实", "事实上"],
     "description": "典型的AI说明文风格，小说中极少使用"},
    {"word": "需要指出的是", "category": "critical", "severity": "high",
     "alternatives": ["其实", "说白了", "坦白说", "实际上"],
     "description": "论文式表达，破坏叙事节奏"},
    {"word": "综上所述", "category": "critical", "severity": "high",
     "alternatives": ["总之", "说到底", "归根结底"],
     "description": "总结性词汇，小说中不自然"},
    {"word": "由此可见", "category": "critical", "severity": "high",
     "alternatives": ["这么看来", "看来", "原来"],
     "description": "逻辑推理词，过于正式"},
    {"word": "不难发现", "category": "critical", "severity": "high",
     "alternatives": ["显然", "明显", "一看就知道"],
     "description": "说教式表达"},
    {"word": "显而易见", "category": "critical", "severity": "high",
     "alternatives": ["明摆着", "谁都看得出", "这还用说"],
     "description": "过于正式的逻辑词"},
    {"word": "毋庸置疑", "category": "critical", "severity": "high",
     "alternatives": ["当然", "那是自然", "没错"],
     "description": "书面语过重"},
    {"word": "不言而喻", "category": "critical", "severity": "high",
     "alternatives": ["不用说", "自然是", "当然"],
     "description": "成语堆砌感"},

    # === 中危词汇（AI高频使用）===
    {"word": "不禁", "category": "warning", "severity": "medium",
     "alternatives": ["忍不住", "情不自禁", "下意识地", "不由自主"],
     "description": "AI高频使用，真人写作较少用"},
    {"word": "不由得", "category": "warning", "severity": "medium",
     "alternatives": ["忍不住", "不自觉地", "情不自禁"],
     "description": "与'不禁'同类，AI偏好"},
    {"word": "不由自主", "category": "warning", "severity": "medium",
     "alternatives": ["忍不住", "不自觉", "下意识"],
     "description": "AI常用来描述动作"},
    {"word": "缓缓", "category": "warning", "severity": "medium",
     "alternatives": ["慢慢", "徐徐", "一点点"],
     "description": "AI偏爱的动作修饰词"},
    {"word": "微微", "category": "warning", "severity": "medium",
     "alternatives": ["轻轻", "略微", "稍稍", "有点"],
     "description": "AI高频程度副词"},
    {"word": "淡淡的", "category": "warning", "severity": "medium",
     "alternatives": ["轻轻的", "隐约的", "若有若无的"],
     "description": "AI常用形容词"},
    {"word": "轻轻地", "category": "warning", "severity": "medium",
     "alternatives": ["轻手轻脚", "小心翼翼", "悄悄"],
     "description": "动作修饰词滥用"},
    {"word": "静静地", "category": "warning", "severity": "medium",
     "alternatives": ["安静地", "默默", "一声不吭"],
     "description": "AI偏好的状态描写"},
    {"word": "默默地", "category": "warning", "severity": "medium",
     "alternatives": ["悄悄", "不声不响", "暗自"],
     "description": "AI常用副词"},
    {"word": "深深地", "category": "warning", "severity": "medium",
     "alternatives": ["狠狠", "重重", "用力"],
     "description": "程度副词滥用"},

    # === 情感套话 ===
    {"word": "心中涌起", "category": "emotional", "severity": "medium",
     "alternatives": ["涌上心头", "心里一阵", "胸口"],
     "description": "AI标准情感描写模板"},
    {"word": "心头一紧", "category": "emotional", "severity": "medium",
     "alternatives": ["心里咯噔一下", "心一沉", "心揪了一下"],
     "description": "紧张情感的套路表达"},
    {"word": "心中一暖", "category": "emotional", "severity": "medium",
     "alternatives": ["心里暖洋洋的", "心头一热", "感动得"],
     "description": "温暖情感的套路表达"},
    {"word": "眼眶泛红", "category": "emotional", "severity": "medium",
     "alternatives": ["眼圈红了", "眼睛湿润", "泪水在眼眶打转"],
     "description": "悲伤情感的套路表达"},
    {"word": "眼眶微红", "category": "emotional", "severity": "medium",
     "alternatives": ["眼圈有点红", "眼睛湿了", "鼻子一酸"],
     "description": "悲伤情感的套路表达"},
    {"word": "嘴角上扬", "category": "emotional", "severity": "medium",
     "alternatives": ["嘴角一翘", "扬起嘴角", "勾起一抹笑"],
     "description": "微笑的套路表达"},
    {"word": "嘴角微扬", "category": "emotional", "severity": "medium",
     "alternatives": ["嘴角弯了弯", "抿嘴一笑", "嘴角带笑"],
     "description": "微笑的套路表达"},
    {"word": "眉头微皱", "category": "emotional", "severity": "medium",
     "alternatives": ["皱了皱眉", "眉头一拧", "微微蹙眉"],
     "description": "思考/不悦的套路表达"},
    {"word": "眉头紧锁", "category": "emotional", "severity": "medium",
     "alternatives": ["皱紧眉头", "眉头拧成一团", "满脸愁容"],
     "description": "担忧的套路表达"},
    {"word": "松了一口气", "category": "emotional", "severity": "low",
     "alternatives": ["如释重负", "心里的石头落了地", "放下心来"],
     "description": "释然情感，使用频率高"},
    {"word": "暗自庆幸", "category": "emotional", "severity": "low",
     "alternatives": ["心里庆幸", "偷着乐", "暗暗高兴"],
     "description": "AI常用心理描写"},
    {"word": "心中暗道", "category": "emotional", "severity": "low",
     "alternatives": ["心想", "暗想", "在心里说"],
     "description": "内心独白的套路表达"},
    {"word": "心中暗想", "category": "emotional", "severity": "low",
     "alternatives": ["心想", "寻思", "琢磨"],
     "description": "内心独白的套路表达"},

    # === 场景套话 ===
    {"word": "阳光透过窗户", "category": "scene", "severity": "medium",
     "alternatives": ["窗外阳光正好", "阳光从窗户照进来", "屋里很亮堂"],
     "description": "AI最爱的开场白之一"},
    {"word": "月光洒在", "category": "scene", "severity": "medium",
     "alternatives": ["月色下", "月光照着", "银色的月光"],
     "description": "夜景描写套路"},
    {"word": "微风拂过", "category": "scene", "severity": "medium",
     "alternatives": ["风吹过来", "起了点风", "有风吹过"],
     "description": "AI常用环境描写"},
    {"word": "空气中弥漫着", "category": "scene", "severity": "medium",
     "alternatives": ["到处都是...的味道", "闻到了", "飘着"],
     "description": "气味描写套路"},
    {"word": "夜幕降临", "category": "scene", "severity": "medium",
     "alternatives": ["天黑了", "入夜后", "夜色渐浓"],
     "description": "AI喜欢的时间过渡"},
    {"word": "晨曦初露", "category": "scene", "severity": "medium",
     "alternatives": ["天刚亮", "东方发白", "太阳刚出来"],
     "description": "过于文艺的时间描写"},

    # === 转折套话 ===
    {"word": "就在这时", "category": "transition", "severity": "medium",
     "alternatives": ["突然", "忽然", "正在这时", "话音未落"],
     "description": "AI最爱的转折方式"},
    {"word": "话音刚落", "category": "transition", "severity": "medium",
     "alternatives": ["话还没说完", "刚说完", "这边话音一落"],
     "description": "对话转折套路"},
    {"word": "与此同时", "category": "transition", "severity": "medium",
     "alternatives": ["这时候", "同时", "另一边"],
     "description": "过于正式的并行叙述"},
    {"word": "正当...之际", "category": "transition", "severity": "medium",
     "alternatives": ["正...的时候", "正在...", "刚要..."],
     "description": "书面化的时间转折"},
    {"word": "然而", "category": "transition", "severity": "low",
     "alternatives": ["可是", "但是", "不过", "可"],
     "description": "过于正式的转折词"},
    {"word": "不料", "category": "transition", "severity": "low",
     "alternatives": ["没想到", "谁知道", "哪知道"],
     "description": "AI常用意外转折"},
    {"word": "岂料", "category": "transition", "severity": "medium",
     "alternatives": ["没想到", "谁知", "哪晓得"],
     "description": "过于书面化"},

    # === 动作描写套话 ===
    {"word": "定定地看着", "category": "warning", "severity": "medium",
     "alternatives": ["直勾勾地看着", "盯着", "目不转睛"],
     "description": "AI常用视线描写"},
    {"word": "一字一顿", "category": "warning", "severity": "medium",
     "alternatives": ["一个字一个字地说", "慢慢说", "咬着字说"],
     "description": "AI常用说话方式描写"},
    {"word": "斩钉截铁", "category": "warning", "severity": "low",
     "alternatives": ["坚定地", "毫不犹豫", "果断"],
     "description": "决心表达的套路"},
    {"word": "目光如炬", "category": "warning", "severity": "medium",
     "alternatives": ["眼神锐利", "目光炯炯", "眼里有光"],
     "description": "成语堆砌"},
    {"word": "若有所思", "category": "warning", "severity": "low",
     "alternatives": ["像在想什么", "出神", "走神"],
     "description": "思考状态的套路表达"},

    # === 其他AI常用词 ===
    {"word": "不得不说", "category": "warning", "severity": "medium",
     "alternatives": ["说实话", "老实说", "确实"],
     "description": "议论式插入语"},
    {"word": "毫无疑问", "category": "warning", "severity": "medium",
     "alternatives": ["肯定", "当然", "没错"],
     "description": "过于绝对的判断词"},
    {"word": "事实上", "category": "warning", "severity": "low",
     "alternatives": ["其实", "实际上", "说白了"],
     "description": "解释性词汇"},
    {"word": "换句话说", "category": "critical", "severity": "high",
     "alternatives": ["也就是说", "说白了", "简单来说"],
     "description": "典型的AI解释句式"},
    {"word": "总而言之", "category": "critical", "severity": "high",
     "alternatives": ["总之", "一句话", "说到底"],
     "description": "总结性词汇"},
]


async def init_ai_vocabulary(db: AsyncSession):
    """初始化AI腔调词汇库

    只在词汇库为空时插入初始数据
    """
    try:
        # 检查是否已有数据
        result = await db.execute(select(func.count(AIVocabulary.id)))
        count = result.scalar()

        if count > 0:
            logger.info(f"AI词汇库已存在 {count} 条数据，跳过初始化")
            return count

        # 插入初始数据
        for vocab_data in INITIAL_VOCABULARY:
            vocab = AIVocabulary(
                word=vocab_data["word"],
                category=vocab_data["category"],
                severity=vocab_data["severity"],
                alternatives=vocab_data["alternatives"],
                description=vocab_data["description"],
                is_system=1
            )
            db.add(vocab)

        await db.commit()
        logger.info(f"成功初始化 {len(INITIAL_VOCABULARY)} 条AI腔调词汇")
        return len(INITIAL_VOCABULARY)

    except Exception as e:
        await db.rollback()
        logger.error(f"初始化AI词汇库失败: {e}")
        raise


async def get_vocabulary_list(db: AsyncSession, category: str = None) -> List[Dict]:
    """获取词汇库列表

    Args:
        db: 数据库会话
        category: 可选，筛选分类

    Returns:
        词汇列表
    """
    query = select(AIVocabulary).order_by(AIVocabulary.severity.desc(), AIVocabulary.usage_count.desc())

    if category:
        query = query.where(AIVocabulary.category == category)

    result = await db.execute(query)
    vocabs = result.scalars().all()

    return [v.to_dict() for v in vocabs]


# ============================================================
# 文本分析工具函数
# ============================================================

def split_sentences(text: str) -> List[str]:
    """将文本分割成句子

    支持中文和英文标点
    """
    # 中英文句子分隔符
    pattern = r'[。！？!?.]+[""]?'

    # 分割
    sentences = re.split(pattern, text)

    # 过滤空句子和太短的句子
    sentences = [s.strip() for s in sentences if s and len(s.strip()) > 2]

    return sentences


def find_word_positions(text: str, word: str) -> List[Dict]:
    """查找词汇在文本中的所有位置

    Returns:
        位置列表 [{"start": int, "end": int, "context": str}, ...]
    """
    positions = []
    start = 0

    while True:
        pos = text.find(word, start)
        if pos == -1:
            break

        # 获取上下文（前后各30个字符）
        context_start = max(0, pos - 30)
        context_end = min(len(text), pos + len(word) + 30)
        context = text[context_start:context_end]

        positions.append({
            "start": pos,
            "end": pos + len(word),
            "context": context
        })

        start = pos + len(word)

    return positions


def calculate_sentence_stats(sentences: List[str]) -> Dict:
    """计算句子统计信息"""
    if not sentences:
        return {
            "count": 0,
            "avg_length": 0,
            "std_dev": 0,
            "min_length": 0,
            "max_length": 0
        }

    lengths = [len(s) for s in sentences]

    return {
        "count": len(sentences),
        "avg_length": round(statistics.mean(lengths), 1),
        "std_dev": round(statistics.stdev(lengths), 1) if len(lengths) > 1 else 0,
        "min_length": min(lengths),
        "max_length": max(lengths)
    }


def get_level_from_score(score: int) -> str:
    """根据分数获取评级"""
    if score >= 80:
        return "自然"
    elif score >= 60:
        return "一般"
    elif score >= 40:
        return "明显"
    else:
        return "严重"


# ============================================================
# 核心检测逻辑
# ============================================================

async def analyze_chapter_tone(
    db: AsyncSession,
    text: str,
    project_id: str = None,
    chapter_id: str = None
) -> Dict[str, Any]:
    """分析章节的AI腔调

    Args:
        db: 数据库会话
        text: 待检测文本
        project_id: 项目ID（可选）
        chapter_id: 章节ID（可选）

    Returns:
        检测结果
    """
    # 1. 获取词汇库
    result = await db.execute(select(AIVocabulary))
    vocabulary = result.scalars().all()

    if not vocabulary:
        # 如果词汇库为空，先初始化
        await init_ai_vocabulary(db)
        result = await db.execute(select(AIVocabulary))
        vocabulary = result.scalars().all()

    # 2. 词汇匹配检测
    issues = []
    matched_vocab_ids = []

    for vocab in vocabulary:
        positions = find_word_positions(text, vocab.word)
        if positions:
            issues.append({
                "type": "vocabulary",
                "severity": vocab.severity,
                "word": vocab.word,
                "category": vocab.category,
                "count": len(positions),
                "positions": positions,
                "alternatives": vocab.alternatives or [],
                "description": vocab.description
            })
            matched_vocab_ids.append(vocab.id)

    # 3. 更新词汇使用次数
    if matched_vocab_ids:
        for vocab_id in matched_vocab_ids:
            await db.execute(
                AIVocabulary.__table__.update()
                .where(AIVocabulary.id == vocab_id)
                .values(usage_count=AIVocabulary.usage_count + 1)
            )

    # 4. 句子统计分析
    sentences = split_sentences(text)
    sentence_stats = calculate_sentence_stats(sentences)

    # 检测句子长度均匀性问题
    if sentence_stats["std_dev"] < 8 and sentence_stats["count"] > 5:
        issues.append({
            "type": "sentence_uniformity",
            "severity": "low",
            "message": "句子长度过于均匀，缺乏节奏变化",
            "avg_length": sentence_stats["avg_length"],
            "std_dev": sentence_stats["std_dev"],
            "suggestion": "尝试混合使用长短句，增加文字节奏感"
        })

    # 5. 连接词检测
    connectors = ["首先", "其次", "最后", "然后", "接着", "随后", "此外", "另外", "同时"]
    connector_count = 0
    connector_details = []

    for conn in connectors:
        count = text.count(conn)
        if count > 0:
            connector_count += count
            connector_details.append({"word": conn, "count": count})

    word_count = len(text)
    connector_ratio = connector_count / max(word_count, 1)

    if connector_ratio > 0.01 and connector_count >= 3:  # 超过1%且至少3个
        issues.append({
            "type": "connector_overuse",
            "severity": "medium",
            "message": f"连接词使用较多（{connector_count}处）",
            "count": connector_count,
            "ratio": round(connector_ratio * 100, 2),
            "details": connector_details,
            "suggestion": "减少'首先、其次、最后'等连接词，让叙述更自然流畅"
        })

    # 6. 计算评分
    # 基础分100，每个问题扣分
    score = 100

    for issue in issues:
        if issue["severity"] == "high":
            score -= issue.get("count", 1) * 8
        elif issue["severity"] == "medium":
            score -= issue.get("count", 1) * 4
        else:
            score -= issue.get("count", 1) * 2

    score = max(0, min(100, score))  # 限制在0-100
    level = get_level_from_score(score)

    # 7. 按严重程度排序问题
    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: (severity_order.get(x["severity"], 3), -x.get("count", 0)))

    # 8. 构建结果
    detection_result = {
        "score": score,
        "level": level,
        "issue_count": len(issues),
        "issues": issues,
        "stats": {
            "word_count": word_count,
            "sentence_count": sentence_stats["count"],
            "avg_sentence_length": sentence_stats["avg_length"],
            "sentence_length_std": sentence_stats["std_dev"]
        },
        "summary": _generate_summary(score, issues)
    }

    # 9. 如果提供了章节ID，保存检测结果
    if chapter_id and project_id:
        await save_tone_analysis(db, project_id, chapter_id, detection_result)

    await db.commit()

    return detection_result


async def save_tone_analysis(
    db: AsyncSession,
    project_id: str,
    chapter_id: str,
    result: Dict
):
    """保存章节检测结果

    如果已存在则更新，否则创建
    """
    # 查找现有记录
    existing = await db.execute(
        select(ChapterToneAnalysis).where(ChapterToneAnalysis.chapter_id == chapter_id)
    )
    analysis = existing.scalars().first()

    if analysis:
        # 更新
        analysis.score = result["score"]
        analysis.level = result["level"]
        analysis.issue_count = result["issue_count"]
        analysis.issues = result["issues"]
        analysis.word_count = result["stats"]["word_count"]
        analysis.sentence_count = result["stats"]["sentence_count"]
        analysis.avg_sentence_length = result["stats"]["avg_sentence_length"]
        analysis.sentence_length_std = result["stats"]["sentence_length_std"]
    else:
        # 创建
        analysis = ChapterToneAnalysis(
            project_id=project_id,
            chapter_id=chapter_id,
            score=result["score"],
            level=result["level"],
            issue_count=result["issue_count"],
            issues=result["issues"],
            word_count=result["stats"]["word_count"],
            sentence_count=result["stats"]["sentence_count"],
            avg_sentence_length=result["stats"]["avg_sentence_length"],
            sentence_length_std=result["stats"]["sentence_length_std"]
        )
        db.add(analysis)


def _generate_summary(score: int, issues: List[Dict]) -> str:
    """生成检测结果摘要"""
    if not issues:
        return "文本风格自然，未发现明显的AI腔调痕迹"

    high_count = sum(1 for i in issues if i["severity"] == "high")
    medium_count = sum(1 for i in issues if i["severity"] == "medium")
    low_count = sum(1 for i in issues if i["severity"] == "low")

    parts = []
    if high_count > 0:
        parts.append(f"{high_count}处高危")
    if medium_count > 0:
        parts.append(f"{medium_count}处中危")
    if low_count > 0:
        parts.append(f"{low_count}处提示")

    level = get_level_from_score(score)

    if level == "严重":
        return f"发现{'/'.join(parts)}问题，AI腔调明显，建议重点优化"
    elif level == "明显":
        return f"发现{'/'.join(parts)}问题，存在较多AI痕迹，建议适当修改"
    elif level == "一般":
        return f"发现{'/'.join(parts)}问题，可以进一步优化"
    else:
        return f"文本较为自然，仅有{'/'.join(parts)}小问题"


async def get_chapter_analysis(db: AsyncSession, chapter_id: str) -> Optional[Dict]:
    """获取章节的检测结果"""
    result = await db.execute(
        select(ChapterToneAnalysis).where(ChapterToneAnalysis.chapter_id == chapter_id)
    )
    analysis = result.scalars().first()

    if analysis:
        return analysis.to_dict()
    return None


async def batch_replace_words(
    text: str,
    replacements: List[Dict]
) -> str:
    """批量替换文本中的词汇

    Args:
        text: 原始文本
        replacements: 替换列表 [{"original": str, "replacement": str}, ...]

    Returns:
        替换后的文本
    """
    # 按位置从后往前替换，避免位置偏移
    # 先收集所有替换位置
    all_replacements = []

    for r in replacements:
        original = r["original"]
        replacement = r["replacement"]

        # 如果指定了位置，只替换该位置
        if "position" in r:
            pos = r["position"]
            all_replacements.append({
                "start": pos["start"],
                "end": pos["end"],
                "replacement": replacement
            })
        else:
            # 替换所有出现
            start = 0
            while True:
                pos = text.find(original, start)
                if pos == -1:
                    break
                all_replacements.append({
                    "start": pos,
                    "end": pos + len(original),
                    "replacement": replacement
                })
                start = pos + len(original)

    # 按位置从后往前排序
    all_replacements.sort(key=lambda x: x["start"], reverse=True)

    # 执行替换
    result = text
    for r in all_replacements:
        result = result[:r["start"]] + r["replacement"] + result[r["end"]:]

    return result
