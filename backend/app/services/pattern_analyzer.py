"""
套路化检测服务 - 跨章节分析
"""
import re
import hashlib
from collections import defaultdict, Counter
from functools import lru_cache
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chapter import Chapter
from app.models.ai_vocabulary import ProjectPatternAnalysis, ChapterPatternCache
from app.logger import get_logger

logger = get_logger(__name__)

# 尝试导入jieba，如果失败则使用简单分词
try:
    import jieba
    import jieba.posseg as pseg
    JIEBA_AVAILABLE = True
    # 静默jieba的日志
    jieba.setLogLevel(jieba.logging.INFO)
    # 预加载词典 (首次调用时加载，后续调用直接使用)
    jieba.initialize()
    logger.info("jieba 词典预加载完成")
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning("jieba未安装，将使用简单分词方式")


# ============================================================
# 模板提取缓存 (LRU Cache)
# ============================================================

# 缓存最多 20000 个句子的模板 (约占用 10-20MB 内存)
TEMPLATE_CACHE_SIZE = 20000

@lru_cache(maxsize=TEMPLATE_CACHE_SIZE)
def extract_template_cached(sentence: str) -> str:
    """带缓存的模板提取 (单句)"""
    if JIEBA_AVAILABLE:
        return _extract_template_with_jieba_impl(sentence)
    return _extract_template_simple_impl(sentence)


# ============================================================
# 情感词汇库
# ============================================================

EMOTION_VOCABULARY = {
    "happy": {
        "keywords": ["笑", "开心", "高兴", "欢喜", "愉快", "欣喜", "快乐", "乐"],
        "expressions": [
            "笑了笑", "笑了起来", "嘴角上扬", "嘴角微扬", "露出笑容",
            "开心地", "高兴地", "欣喜", "喜悦", "乐呵呵"
        ]
    },
    "sad": {
        "keywords": ["哭", "泪", "悲", "伤心", "难过", "痛苦", "忧伤"],
        "expressions": [
            "叹了口气", "叹气", "眼眶泛红", "眼眶湿润", "流下眼泪",
            "泪流满面", "悲伤地", "伤心地", "难过地", "黯然"
        ]
    },
    "angry": {
        "keywords": ["怒", "气", "愤", "恼", "火"],
        "expressions": [
            "怒道", "怒吼", "冷哼", "大怒", "勃然大怒",
            "气愤地", "愤怒地", "怒气冲冲", "火冒三丈"
        ]
    },
    "fear": {
        "keywords": ["怕", "惧", "恐", "惊", "慌"],
        "expressions": [
            "害怕", "恐惧", "惊恐", "惊慌", "慌张",
            "心惊胆战", "胆战心惊", "瑟瑟发抖"
        ]
    },
    "surprise": {
        "keywords": ["惊", "讶", "愕"],
        "expressions": [
            "惊讶", "吃惊", "震惊", "愕然", "目瞪口呆",
            "大吃一惊", "惊呆了", "不敢相信"
        ]
    }
}

# ============================================================
# 动词语义归类表 (用于模板抽象化)
# ============================================================

VERB_SEMANTIC_GROUPS = {
    # 视觉动词
    "[视觉]": {"看", "望", "盯", "瞧", "瞅", "观察", "注视", "凝视", "打量", "审视", "眺望", "俯视", "仰望", "环顾", "扫视"},
    # 言语动词
    "[言语]": {"说", "道", "讲", "问", "答", "回答", "回应", "喊", "叫", "吼", "嚷", "嘟囔", "低语", "呢喃", "轻声"},
    # 移动动词
    "[移动]": {"走", "跑", "冲", "奔", "飞", "跳", "爬", "滚", "溜", "窜", "闯", "踱", "漫步", "疾步", "快步"},
    # 手部动作
    "[手动]": {"拿", "抓", "握", "捏", "拎", "提", "举", "放", "扔", "丢", "递", "接", "推", "拉", "拽", "按", "摸", "碰", "触"},
    # 情感动词
    "[情感]": {"笑", "哭", "怒", "惊", "喜", "悲", "恨", "爱", "怕", "慌", "愁", "叹", "愣", "呆"},
    # 思维动词
    "[思维]": {"想", "思", "考虑", "琢磨", "思索", "寻思", "盘算", "回忆", "记得", "忘记", "明白", "理解", "懂", "知道"},
    # 身体姿态
    "[姿态]": {"站", "坐", "躺", "蹲", "趴", "倚", "靠", "卧", "跪", "立"},
    # 头部动作
    "[头动]": {"点头", "摇头", "抬头", "低头", "转头", "回头", "侧头", "仰头", "埋头"},
    # 表情动作
    "[表情]": {"皱眉", "蹙眉", "挑眉", "扬眉", "眯眼", "瞪眼", "闭眼", "睁眼", "咬唇", "抿唇", "撇嘴", "嘟嘴"},
}

# 构建反向映射: 动词 -> 语义标签
VERB_TO_SEMANTIC = {}
for semantic_tag, verbs in VERB_SEMANTIC_GROUPS.items():
    for verb in verbs:
        VERB_TO_SEMANTIC[verb] = semantic_tag


# 开场类型关键词
OPENING_KEYWORDS = {
    "time": ["清晨", "早上", "上午", "中午", "下午", "傍晚", "黄昏", "夜晚", "深夜",
             "凌晨", "天亮", "天黑", "日出", "日落", "午后", "夜深", "拂晓", "黎明",
             "第二天", "第三天", "几天后", "一周后", "一个月后", "次日"],
    "weather": ["阳光", "月光", "星光", "细雨", "大雨", "暴雨", "风", "雪", "云", "雾",
                "晴朗", "阴沉", "乌云", "雷电", "闪电"],
    "action": ["走进", "推开", "打开", "关上", "站在", "坐在", "躺在", "跑向", "冲向"],
    "dialogue": ["「", "\"", "'", "\u201c", "『"],
}


# ============================================================
# 工具函数
# ============================================================

def split_sentences(text: str) -> List[str]:
    """将文本分割成句子"""
    pattern = r'[。！？!?]+"?'
    sentences = re.split(pattern, text)
    sentences = [s.strip() for s in sentences if s and len(s.strip()) > 3]
    return sentences


def simple_tokenize(sentence: str) -> List[Tuple[str, str]]:
    """简单分词(不依赖jieba)

    返回 [(word, pos), ...] 格式, pos是简化的词性标记
    """
    result = []

    # 简单的词性判断规则
    pronouns = set("我你他她它们您咱俺")

    # 按字符遍历，简单切分
    i = 0
    while i < len(sentence):
        char = sentence[i]

        if char in pronouns:
            result.append((char, 'r'))  # 代词
        elif '\u4e00' <= char <= '\u9fff':
            # 中文字符，简单地按单字处理或尝试匹配常见词
            result.append((char, 'n'))  # 默认为名词
        else:
            result.append((char, 'x'))  # 其他

        i += 1

    return result


def _extract_template_with_jieba_impl(sentence: str) -> str:
    """使用jieba提取句子模板 (内部实现, 被缓存包装)"""
    if not JIEBA_AVAILABLE:
        return _extract_template_simple_impl(sentence)

    result = []
    words = pseg.cut(sentence)

    for word, flag in words:
        if flag.startswith('n'):  # 名词
            result.append('[名词]')
        elif flag == 'r':  # 代词
            result.append('[代词]')
        elif flag.startswith('v'):  # 动词 - 语义归类
            # 优先检查语义归类表
            semantic = VERB_TO_SEMANTIC.get(word)
            if semantic:
                result.append(semantic)
            else:
                # 未归类的动词保留原词
                result.append(word)
        elif flag == 'd':  # 副词
            result.append('[副词]')
        elif flag.startswith('a'):  # 形容词
            result.append('[形容词]')
        elif flag == 'm':  # 数词
            result.append('[数词]')
        elif flag == 'p':  # 介词 - 保留
            result.append(word)
        elif flag in ('c', 'u', 'e', 'y', 'o', 'w'):  # 连词、助词等 - 保留
            result.append(word)
        else:
            result.append(word)

    # 合并连续的相同占位符
    merged = []
    prev = None
    for item in result:
        if item.startswith('[') and item == prev:
            continue
        merged.append(item)
        prev = item

    return ''.join(merged)


def _extract_template_simple_impl(sentence: str) -> str:
    """简单的模板提取 (内部实现, 被缓存包装)

    策略: 保留动词/连接词/标点, 替换名词性成分
    """
    # 常见动词（保留）
    common_verbs = {
        "是", "有", "在", "说", "道", "看", "想", "知道", "觉得", "认为",
        "走", "来", "去", "跑", "站", "坐", "躺", "笑", "哭", "喊", "叫",
        "做", "给", "让", "把", "被", "对", "向", "从", "到", "过",
        "打开", "关上", "拿起", "放下", "抬头", "低头", "转身", "回头",
        "开始", "结束", "继续", "停止", "出现", "消失", "发现", "听到",
    }

    # 常见连接词和助词（保留）
    keep_words = {
        "的", "地", "得", "了", "着", "过", "吗", "呢", "吧", "啊",
        "和", "与", "或", "但", "但是", "然而", "因为", "所以", "如果",
        "就", "都", "也", "还", "又", "再", "才", "只", "很", "太",
        "不", "没", "没有", "不是", "不会", "不能",
    }

    # 代词
    pronouns = {"我", "你", "他", "她", "它", "我们", "你们", "他们", "她们", "它们",
                "这", "那", "这个", "那个", "这些", "那些", "自己", "大家", "谁"}

    result = []
    i = 0
    text = sentence

    while i < len(text):
        # 尝试匹配双字词
        if i + 1 < len(text):
            two_char = text[i:i+2]
            if two_char in common_verbs or two_char in keep_words:
                result.append(two_char)
                i += 2
                continue
            if two_char in pronouns:
                result.append('[代词]')
                i += 2
                continue

        # 单字匹配
        char = text[i]
        if char in common_verbs or char in keep_words:
            result.append(char)
        elif char in pronouns:
            result.append('[代词]')
        elif char in '，。！？、；：""''（）【】《》…—':
            result.append(char)
        elif '\u4e00' <= char <= '\u9fff':
            # 中文字符，标记为名词
            if result and result[-1] == '[名词]':
                pass  # 合并连续名词
            else:
                result.append('[名词]')
        else:
            result.append(char)

        i += 1

    return ''.join(result)


def extract_template(sentence: str) -> str:
    """提取句子模板 (使用缓存)"""
    return extract_template_cached(sentence)


def extract_templates_batch(sentences: List[str]) -> List[str]:
    """批量提取句子模板

    优化策略:
    1. 利用 LRU 缓存避免重复计算
    2. 对于大批量句子，先统计重复句子

    Args:
        sentences: 句子列表

    Returns:
        模板列表
    """
    if not sentences:
        return []

    # 统计句子出现次数，避免重复计算
    sentence_set = set(sentences)

    # 预计算所有唯一句子的模板
    template_map = {}
    for sent in sentence_set:
        template_map[sent] = extract_template_cached(sent)

    # 按原顺序返回模板
    return [template_map[sent] for sent in sentences]


def get_template_cache_info() -> Dict:
    """获取模板缓存统计信息"""
    info = extract_template_cached.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
        "hit_rate": info.hits / (info.hits + info.misses) if (info.hits + info.misses) > 0 else 0
    }


def clear_template_cache():
    """清除模板缓存"""
    extract_template_cached.cache_clear()
    logger.info("模板缓存已清除")


# 兼容旧接口
def extract_template_with_jieba(sentence: str) -> str:
    """使用jieba提取句子模板 (兼容旧接口)"""
    return _extract_template_with_jieba_impl(sentence)


def extract_template_simple(sentence: str) -> str:
    """简单的模板提取 (兼容旧接口)"""
    return _extract_template_simple_impl(sentence)


def template_similarity(t1: str, t2: str) -> float:
    """计算两个模板的相似度 (0-1)

    使用优化的编辑距离算法，考虑占位符的特殊性
    """
    if t1 == t2:
        return 1.0

    len1, len2 = len(t1), len(t2)
    if len1 == 0 or len2 == 0:
        return 0.0

    # 长度差异过大，直接返回低相似度
    if abs(len1 - len2) > max(len1, len2) * 0.5:
        return 0.0

    # 使用简化的编辑距离 (空间优化版)
    if len1 > len2:
        t1, t2 = t2, t1
        len1, len2 = len2, len1

    prev_row = list(range(len2 + 1))

    for i, c1 in enumerate(t1):
        curr_row = [i + 1]
        for j, c2 in enumerate(t2):
            # 插入、删除、替换的代价
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (0 if c1 == c2 else 1)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    distance = prev_row[-1]
    max_len = max(len1, len2)

    return 1.0 - (distance / max_len)


def cluster_templates_similar(templates: List[Dict], threshold: float = 0.7) -> List[List[Dict]]:
    """聚类相似模板 (优化版: 两阶段聚类)

    阶段1: 精确匹配快速聚类 O(n)
    阶段2: 对精确簇的代表模板进行相似度合并

    Args:
        templates: 模板列表
        threshold: 相似度阈值 (默认0.7)

    Returns:
        聚类结果
    """
    if not templates:
        return []

    # 过滤太短的模板
    valid_templates = [t for t in templates if len(t.get("template", "")) > 5]

    if not valid_templates:
        return []

    # ========== 阶段1: 精确匹配快速聚类 ==========
    exact_clusters = defaultdict(list)
    for item in valid_templates:
        template = item.get("template", "")
        exact_clusters[template].append(item)

    # 转换为列表，只保留出现2次以上的
    cluster_list = []
    for template, items in exact_clusters.items():
        if len(items) >= 2:
            cluster_list.append({
                "representative": template,
                "items": items
            })

    # 如果簇数量不多，直接返回
    if len(cluster_list) <= 50:
        # ========== 阶段2: 相似度合并 ==========
        merged = _merge_similar_clusters(cluster_list, threshold)
        result = [c["items"] for c in merged if len(c["items"]) >= 2]
        result.sort(key=lambda x: len(x), reverse=True)
        return result
    else:
        # 簇太多，跳过相似度合并，直接返回精确聚类结果
        result = [c["items"] for c in cluster_list]
        result.sort(key=lambda x: len(x), reverse=True)
        return result


def _merge_similar_clusters(clusters: List[Dict], threshold: float) -> List[Dict]:
    """合并相似的簇

    Args:
        clusters: [{"representative": str, "items": list}, ...]
        threshold: 相似度阈值

    Returns:
        合并后的簇列表
    """
    if len(clusters) <= 1:
        return clusters

    # 标记每个簇是否已被合并
    merged_into = list(range(len(clusters)))  # 并查集

    def find(x):
        if merged_into[x] != x:
            merged_into[x] = find(merged_into[x])
        return merged_into[x]

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            merged_into[rx] = ry

    # 只比较代表模板之间的相似度 (簇数量已被限制在50以内)
    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            rep_i = clusters[i]["representative"]
            rep_j = clusters[j]["representative"]

            # 长度差异过大，跳过
            if abs(len(rep_i) - len(rep_j)) > max(len(rep_i), len(rep_j)) * 0.4:
                continue

            sim = template_similarity(rep_i, rep_j)
            if sim >= threshold:
                union(i, j)

    # 根据并查集合并
    merged_clusters = defaultdict(lambda: {"representative": "", "items": []})
    for i, cluster in enumerate(clusters):
        root = find(i)
        if not merged_clusters[root]["representative"]:
            merged_clusters[root]["representative"] = cluster["representative"]
        merged_clusters[root]["items"].extend(cluster["items"])

    return list(merged_clusters.values())


def cluster_templates(templates: List[Dict]) -> List[List[Dict]]:
    """聚类相似模板 (兼容旧接口，使用优化算法)"""
    return cluster_templates_similar(templates, threshold=0.7)


# ============================================================
# N-gram 模式检测 (检测连续句子的叙事结构套路)
# ============================================================

def extract_sentence_type(template: str) -> str:
    """从模板提取句子类型标签

    将复杂模板简化为类型标签，用于 N-gram 分析
    """
    # 检测主要特征
    has_dialogue = any(marker in template for marker in ['「', '"', "'", '：'])
    has_action = any(tag in template for tag in ['[视觉]', '[移动]', '[手动]', '[姿态]', '[头动]'])
    has_emotion = '[情感]' in template or any(tag in template for tag in ['[表情]'])
    has_speech = '[言语]' in template
    has_thought = '[思维]' in template

    # 生成类型标签
    if has_dialogue or has_speech:
        return 'D'  # Dialogue 对话
    elif has_thought:
        return 'T'  # Thought 思维
    elif has_emotion:
        return 'E'  # Emotion 情感
    elif has_action:
        return 'A'  # Action 动作
    else:
        return 'N'  # Narrative 叙述


def extract_ngrams(templates: List[Dict], n: int = 2) -> List[Dict]:
    """提取 N-gram 模式

    Args:
        templates: 按章节和位置排序的模板列表
        n: N-gram 大小 (2 或 3)

    Returns:
        N-gram 模式列表
    """
    if len(templates) < n:
        return []

    # 按章节分组
    chapters = defaultdict(list)
    for t in templates:
        chapters[t.get("chapter_id")].append(t)

    # 对每章按位置排序
    for chapter_id in chapters:
        chapters[chapter_id].sort(key=lambda x: x.get("position", 0))

    ngrams = []

    for chapter_id, chapter_templates in chapters.items():
        if len(chapter_templates) < n:
            continue

        # 提取句子类型序列
        types = [extract_sentence_type(t.get("template", "")) for t in chapter_templates]

        # 生成 N-gram
        for i in range(len(types) - n + 1):
            ngram_types = tuple(types[i:i + n])
            ngram_templates = chapter_templates[i:i + n]

            ngrams.append({
                "pattern": '→'.join(ngram_types),
                "types": ngram_types,
                "chapter_id": chapter_id,
                "chapter_number": chapter_templates[0].get("chapter_number"),
                "start_position": i,
                "sentences": [t.get("text", "") for t in ngram_templates]
            })

    return ngrams


def analyze_ngram_patterns(templates: List[Dict]) -> Dict:
    """分析 N-gram 模式，检测叙事结构套路

    Returns:
        {
            "bigram_patterns": [...],   # 2-gram 模式
            "trigram_patterns": [...],  # 3-gram 模式
            "repetitive_sequences": [...],  # 重复的叙事序列
            "diversity_score": int  # 叙事多样性评分
        }
    """
    # 提取 2-gram 和 3-gram
    bigrams = extract_ngrams(templates, n=2)
    trigrams = extract_ngrams(templates, n=3)

    # 统计模式频率
    bigram_counter = Counter(ng["pattern"] for ng in bigrams)
    trigram_counter = Counter(ng["pattern"] for ng in trigrams)

    # 找出高频模式 (出现3次以上)
    repetitive_bigrams = []
    for pattern, count in bigram_counter.most_common(10):
        if count >= 3:
            # 找出所有实例
            examples = [ng for ng in bigrams if ng["pattern"] == pattern][:3]
            repetitive_bigrams.append({
                "pattern": pattern,
                "count": count,
                "description": _describe_ngram_pattern(pattern),
                "examples": [{"chapter": ex["chapter_number"], "sentences": ex["sentences"]} for ex in examples]
            })

    repetitive_trigrams = []
    for pattern, count in trigram_counter.most_common(10):
        if count >= 3:
            examples = [ng for ng in trigrams if ng["pattern"] == pattern][:3]
            repetitive_trigrams.append({
                "pattern": pattern,
                "count": count,
                "description": _describe_ngram_pattern(pattern),
                "examples": [{"chapter": ex["chapter_number"], "sentences": ex["sentences"]} for ex in examples]
            })

    # 计算叙事多样性评分
    total_bigrams = len(bigrams)
    unique_bigrams = len(bigram_counter)

    if total_bigrams > 0:
        diversity_ratio = unique_bigrams / total_bigrams
        # 调整为 0-100 分
        diversity_score = min(100, int(diversity_ratio * 200))
    else:
        diversity_score = 100

    return {
        "bigram_patterns": repetitive_bigrams,
        "trigram_patterns": repetitive_trigrams,
        "total_bigrams": total_bigrams,
        "unique_bigrams": unique_bigrams,
        "diversity_score": diversity_score
    }


def _describe_ngram_pattern(pattern: str) -> str:
    """为 N-gram 模式生成人类可读的描述"""
    type_names = {
        'D': '对话',
        'T': '思维',
        'E': '情感',
        'A': '动作',
        'N': '叙述'
    }

    parts = pattern.split('→')
    descriptions = [type_names.get(p, p) for p in parts]

    return ' → '.join(descriptions)


def analyze_opening_type(sentence: str) -> str:
    """分析开场类型"""
    # 检查是否是对话开场
    for marker in OPENING_KEYWORDS["dialogue"]:
        if sentence.strip().startswith(marker):
            return "dialogue"

    # 检查时间开场
    for keyword in OPENING_KEYWORDS["time"]:
        if keyword in sentence[:20]:  # 只检查开头20个字符
            return "time"

    # 检查天气开场
    for keyword in OPENING_KEYWORDS["weather"]:
        if keyword in sentence[:30]:
            return "weather"

    # 检查动作开场
    for keyword in OPENING_KEYWORDS["action"]:
        if keyword in sentence[:15]:
            return "action"

    return "other"


def analyze_emotion_in_text(text: str) -> Dict[str, List[str]]:
    """分析文本中的情感表达"""
    found = defaultdict(list)

    for emotion, config in EMOTION_VOCABULARY.items():
        for expr in config["expressions"]:
            if expr in text:
                if expr not in found[emotion]:
                    found[emotion].append(expr)

    return dict(found)


def count_emotion_expressions(chapters_content: List[str]) -> Dict[str, Counter]:
    """统计所有章节中的情感表达使用次数"""
    emotion_counts = {emotion: Counter() for emotion in EMOTION_VOCABULARY.keys()}

    full_text = '\n'.join(chapters_content)

    for emotion, config in EMOTION_VOCABULARY.items():
        for expr in config["expressions"]:
            count = full_text.count(expr)
            if count > 0:
                emotion_counts[emotion][expr] = count

    return emotion_counts


# ============================================================
# 核心分析函数
# ============================================================

async def analyze_project_patterns(
    db: AsyncSession,
    project_id: str,
    min_chapters: int = 5
) -> Dict[str, Any]:
    """分析项目的套路化程度

    Args:
        db: 数据库会话
        project_id: 项目ID
        min_chapters: 最少需要的章节数

    Returns:
        分析结果
    """
    # 1. 获取所有章节
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    if len(chapters) < min_chapters:
        return {
            "status": "insufficient_data",
            "message": f"需要至少{min_chapters}个章节才能进行套路化分析",
            "current_chapters": len(chapters)
        }

    # 2. 提取所有句子并标记来源
    all_sentences = []
    chapters_content = []

    for chapter in chapters:
        if not chapter.content:
            continue

        chapters_content.append(chapter.content)
        sentences = split_sentences(chapter.content)

        for i, sent in enumerate(sentences):
            all_sentences.append({
                "text": sent,
                "chapter_id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "chapter_title": chapter.title,
                "position": i,
                "is_opening": i < 3,
                "is_ending": i >= len(sentences) - 3 if len(sentences) > 3 else False
            })

    if not all_sentences:
        return {
            "status": "no_content",
            "message": "章节内容为空"
        }

    # 3. 句子模板化 (使用批量提取 + 缓存)
    logger.info(f"开始分析项目 {project_id}，共 {len(chapters)} 章，{len(all_sentences)} 句")
    logger.info("[1/6] 开始句子模板化...")

    # 提取所有句子文本
    sentence_texts = [sent["text"] for sent in all_sentences]

    # 批量提取模板 (利用缓存加速)
    template_strs = extract_templates_batch(sentence_texts)

    # 构建模板列表
    templates = []
    for i, (sent, template) in enumerate(zip(all_sentences, template_strs)):
        templates.append({
            **sent,
            "template": template
        })
        # 每处理 1000 句输出一次进度
        if (i + 1) % 1000 == 0:
            logger.info(f"[1/6] 模板化进度: {i + 1}/{len(all_sentences)}")

    # 输出缓存统计
    cache_info = get_template_cache_info()
    logger.info(f"[1/6] 模板化完成，共 {len(templates)} 个模板 (缓存命中率: {cache_info['hit_rate']:.1%})")

    # 4. 聚类相似模板
    logger.info("[2/6] 开始模板聚类...")
    clusters = cluster_templates(templates)
    logger.info(f"[2/6] 聚类完成，共 {len(clusters)} 个簇")

    # 5. 找出重复模式（出现3次以上）
    patterns = []
    for cluster in clusters:
        if len(cluster) >= 3:
            # 获取涉及的章节
            chapter_numbers = list(set(c["chapter_number"] for c in cluster))
            chapter_numbers.sort()

            patterns.append({
                "template": cluster[0]["template"],
                "count": len(cluster),
                "examples": [c["text"] for c in cluster[:5]],
                "chapters": chapter_numbers,
                "is_opening_pattern": all(c["is_opening"] for c in cluster),
                "is_ending_pattern": all(c["is_ending"] for c in cluster)
            })

    # 按出现次数排序
    patterns.sort(key=lambda x: x["count"], reverse=True)
    logger.info(f"[3/6] 发现 {len(patterns)} 个重复模式")

    # 6. 分析开场模式
    logger.info("[4/6] 分析开场模式...")
    opening_analysis = analyze_openings(all_sentences, len(chapters))

    # 7. 分析情感词汇多样性
    logger.info("[5/6] 分析情感词汇多样性...")
    emotion_diversity = analyze_emotion_diversity(chapters_content)

    # 8. N-gram 叙事结构分析 (新增)
    logger.info("[6/6] N-gram 叙事结构分析...")
    ngram_analysis = analyze_ngram_patterns(templates)

    # 9. 计算套路化评分 (传入 N-gram 分析结果)
    score = calculate_pattern_score(
        patterns, opening_analysis, emotion_diversity,
        len(chapters), ngram_analysis
    )
    level = get_pattern_level(score)

    # 10. 生成建议 (包含 N-gram 建议)
    suggestions = generate_pattern_suggestions(
        patterns, opening_analysis, emotion_diversity, ngram_analysis
    )

    # 11. 构建结果
    analysis_result = {
        "status": "success",
        "score": score,
        "level": level,
        "chapters_analyzed": len(chapters),
        "patterns_found": len(patterns),
        "top_patterns": patterns[:10],
        "opening_analysis": opening_analysis,
        "emotion_diversity": emotion_diversity,
        "ngram_analysis": ngram_analysis,  # 新增
        "suggestions": suggestions
    }

    # 12. 保存分析结果
    await save_pattern_analysis(db, project_id, analysis_result)
    await db.commit()

    logger.info(f"项目 {project_id} 分析完成: score={score}, patterns={len(patterns)}")

    return analysis_result


def analyze_openings(all_sentences: List[Dict], total_chapters: int) -> Dict:
    """分析章节开场模式"""
    # 获取每章的第一句
    openings = [s for s in all_sentences if s["position"] == 0]

    # 分类统计
    categories = Counter()
    opening_examples = defaultdict(list)

    for opening in openings:
        opening_type = analyze_opening_type(opening["text"])
        categories[opening_type] += 1
        if len(opening_examples[opening_type]) < 3:
            opening_examples[opening_type].append({
                "chapter": opening["chapter_number"],
                "text": opening["text"][:50] + "..." if len(opening["text"]) > 50 else opening["text"]
            })

    # 找出主导类型
    if categories:
        dominant = categories.most_common(1)[0]
        dominant_type = dominant[0]
        dominant_count = dominant[1]
        dominant_ratio = dominant_count / len(openings) if openings else 0
    else:
        dominant_type = "unknown"
        dominant_count = 0
        dominant_ratio = 0

    # 生成建议
    suggestion = ""
    if dominant_ratio > 0.6:
        type_names = {
            "time": "时间",
            "weather": "天气/环境",
            "dialogue": "对话",
            "action": "动作",
            "other": "其他"
        }
        suggestion = f"{int(dominant_ratio * 100)}%的章节以{type_names.get(dominant_type, dominant_type)}开场，建议尝试更多样的开场方式"

    return {
        "total_chapters": len(openings),
        "categories": dict(categories),
        "examples": dict(opening_examples),
        "dominant_type": dominant_type,
        "dominant_count": dominant_count,
        "dominant_ratio": round(dominant_ratio, 2),
        "is_monotonous": dominant_ratio > 0.6,
        "suggestion": suggestion
    }


def analyze_emotion_diversity(chapters_content: List[str]) -> Dict:
    """分析情感词汇多样性 (改进版: 修复样本量问题)"""
    emotion_counts = count_emotion_expressions(chapters_content)

    result = {}
    total_expressions = 0
    total_unique = 0

    for emotion, counter in emotion_counts.items():
        if counter:
            expressions = counter.most_common(10)
            total = sum(counter.values())
            unique = len(counter)

            # 计算集中度（最常用的表达占比）
            top_expr = expressions[0] if expressions else (None, 0)
            concentration = top_expr[1] / total if total > 0 else 0

            result[emotion] = {
                "expressions": expressions,
                "total_count": total,
                "unique_count": unique,
                "concentration": round(concentration, 2),
                "top_expression": top_expr[0],
                "top_count": top_expr[1]
            }

            total_expressions += total
            total_unique += unique

    # 计算整体多样性评分 (改进版)
    if total_expressions == 0:
        # 没有使用情感词汇，无法评判
        diversity_score = 50
        score_note = "未检测到情感表达"
    elif total_expressions < 10:
        # 样本不足，给出中等评分
        diversity_score = 60
        score_note = "样本不足"
    else:
        # 正常计算：综合考虑多样性比例和绝对数量
        diversity_ratio = total_unique / total_expressions

        # 基础分 = 比例分数 (0-70分)
        base_score = int(diversity_ratio * 200)

        # 加分项：绝对数量越多，说明表达越丰富 (0-30分)
        quantity_bonus = min(30, total_unique * 3)

        diversity_score = min(100, base_score + quantity_bonus)
        score_note = None

    # 找出最单一的情感表达
    most_concentrated = None
    max_concentration = 0
    for emotion, data in result.items():
        if data["concentration"] > max_concentration and data["total_count"] >= 5:
            max_concentration = data["concentration"]
            most_concentrated = emotion

    suggestion = ""
    if most_concentrated and max_concentration > 0.7:
        emotion_names = {
            "happy": "开心", "sad": "悲伤", "angry": "愤怒",
            "fear": "恐惧", "surprise": "惊讶"
        }
        top_expr = result[most_concentrated]["top_expression"]
        suggestion = f"表达「{emotion_names.get(most_concentrated, most_concentrated)}」时，{int(max_concentration * 100)}%使用「{top_expr}」，建议扩展情感表达词汇"

    return {
        "emotions": result,
        "diversity_score": diversity_score,
        "total_expressions": total_expressions,
        "total_unique": total_unique,
        "most_concentrated_emotion": most_concentrated,
        "suggestion": suggestion
    }


def calculate_pattern_score(
    patterns: List[Dict],
    opening_analysis: Dict,
    emotion_diversity: Dict,
    chapter_count: int,
    ngram_analysis: Dict = None
) -> int:
    """计算套路化评分(0-100, 越高越多样) - 改进版: 平衡权重

    评分维度及权重:
    - 句式重复: 最多扣 30 分
    - 开场单一: 最多扣 20 分
    - 情感单一: 最多扣 20 分
    - N-gram 叙事结构: 最多扣 30 分
    """
    score = 100

    # 1. 句式重复扣分 (最多扣30分)
    pattern_penalty = 0
    for pattern in patterns[:10]:
        repeat_ratio = pattern["count"] / max(chapter_count, 1)
        if repeat_ratio > 0.5:
            pattern_penalty += 5
        elif repeat_ratio > 0.3:
            pattern_penalty += 3
        elif repeat_ratio > 0.2:
            pattern_penalty += 2
        else:
            pattern_penalty += 1
    score -= min(30, pattern_penalty)

    # 2. 开场单一扣分 (最多扣20分)
    if opening_analysis.get("is_monotonous"):
        dominant_ratio = opening_analysis.get("dominant_ratio", 0)
        if dominant_ratio > 0.8:
            score -= 20
        elif dominant_ratio > 0.6:
            score -= 12
        else:
            score -= 6

    # 3. 情感词汇单一扣分 (最多扣20分)
    emotion_score = emotion_diversity.get("diversity_score", 100)
    if emotion_score < 40:
        score -= 20
    elif emotion_score < 60:
        score -= 12
    elif emotion_score < 80:
        score -= 6

    # 4. N-gram 叙事结构扣分 (最多扣30分)
    if ngram_analysis:
        ngram_diversity = ngram_analysis.get("diversity_score", 100)
        bigram_count = len(ngram_analysis.get("bigram_patterns", []))
        trigram_count = len(ngram_analysis.get("trigram_patterns", []))

        # 低多样性扣分
        if ngram_diversity < 30:
            score -= 15
        elif ngram_diversity < 50:
            score -= 10
        elif ngram_diversity < 70:
            score -= 5

        # 高频重复模式扣分
        if bigram_count > 5:
            score -= 8
        elif bigram_count > 3:
            score -= 5
        elif bigram_count > 1:
            score -= 2

        if trigram_count > 3:
            score -= 7
        elif trigram_count > 1:
            score -= 3

    return max(0, min(100, score))


def get_pattern_level(score: int) -> str:
    """根据分数获取评级"""
    if score >= 80:
        return "多样丰富"
    elif score >= 60:
        return "较为多样"
    elif score >= 40:
        return "套路化明显"
    else:
        return "高度套路化"


def generate_pattern_suggestions(
    patterns: List[Dict],
    opening_analysis: Dict,
    emotion_diversity: Dict,
    ngram_analysis: Dict = None
) -> List[str]:
    """生成改进建议 (改进版: 包含 N-gram 建议)"""
    suggestions = []

    # 重复模式建议
    for pattern in patterns[:5]:
        if pattern["count"] >= 5:
            template = pattern["template"]
            # 简化模板显示
            if len(template) > 30:
                template = template[:30] + "..."
            suggestions.append(f"「{template}」出现{pattern['count']}次，建议使用更多样的表达方式")

    # 开场建议
    if opening_analysis.get("suggestion"):
        suggestions.append(opening_analysis["suggestion"])

    # 情感建议
    if emotion_diversity.get("suggestion"):
        suggestions.append(emotion_diversity["suggestion"])

    # N-gram 叙事结构建议 (新增)
    if ngram_analysis:
        # 高频 bigram 模式建议
        for bp in ngram_analysis.get("bigram_patterns", [])[:3]:
            if bp["count"] >= 5:
                suggestions.append(
                    f"叙事模式「{bp['description']}」出现{bp['count']}次，尝试打破固定的句式节奏"
                )

        # 高频 trigram 模式建议
        for tp in ngram_analysis.get("trigram_patterns", [])[:2]:
            if tp["count"] >= 4:
                suggestions.append(
                    f"三句式模式「{tp['description']}」频繁出现，建议增加叙事结构变化"
                )

        # 整体多样性建议
        ngram_diversity = ngram_analysis.get("diversity_score", 100)
        if ngram_diversity < 40:
            suggestions.append("叙事节奏较为单一，建议穿插不同类型的句子组合")

    return suggestions


async def save_pattern_analysis(db: AsyncSession, project_id: str, result: Dict):
    """保存分析结果"""
    # 查找现有记录
    existing = await db.execute(
        select(ProjectPatternAnalysis).where(ProjectPatternAnalysis.project_id == project_id)
    )
    analysis = existing.scalars().first()

    if analysis:
        # 更新
        analysis.score = result["score"]
        analysis.level = result["level"]
        analysis.chapters_analyzed = result["chapters_analyzed"]
        analysis.patterns_found = result["patterns_found"]
        analysis.top_patterns = result["top_patterns"]
        analysis.opening_analysis = result["opening_analysis"]
        analysis.emotion_diversity = result["emotion_diversity"]
        analysis.ngram_analysis = result.get("ngram_analysis")  # 新增
        analysis.suggestions = result["suggestions"]
        analysis.detection_version = "2.0"  # 更新版本号
    else:
        # 创建
        analysis = ProjectPatternAnalysis(
            project_id=project_id,
            score=result["score"],
            level=result["level"],
            chapters_analyzed=result["chapters_analyzed"],
            patterns_found=result["patterns_found"],
            top_patterns=result["top_patterns"],
            opening_analysis=result["opening_analysis"],
            emotion_diversity=result["emotion_diversity"],
            ngram_analysis=result.get("ngram_analysis"),  # 新增
            suggestions=result["suggestions"]
        )
        db.add(analysis)


async def get_pattern_analysis(db: AsyncSession, project_id: str) -> Optional[Dict]:
    """获取已保存的分析结果"""
    result = await db.execute(
        select(ProjectPatternAnalysis).where(ProjectPatternAnalysis.project_id == project_id)
    )
    analysis = result.scalars().first()

    if analysis:
        return analysis.to_dict()
    return None


# ============================================================
# 增量分析功能
# ============================================================

ANALYSIS_VERSION = "2.0"


def compute_content_hash(content: str) -> str:
    """计算内容的MD5哈希"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def analyze_single_chapter(
    chapter_id: str,
    chapter_number: int,
    content: str,
    title: str = ""
) -> Dict:
    """分析单个章节，返回可缓存的结果

    Args:
        chapter_id: 章节ID
        chapter_number: 章节序号
        content: 章节内容
        title: 章节标题

    Returns:
        章节分析结果
    """
    if not content:
        return {
            "chapter_id": chapter_id,
            "chapter_number": chapter_number,
            "templates": [],
            "sentence_count": 0,
            "opening_type": None,
            "emotion_stats": {}
        }

    # 分句
    sentences = split_sentences(content)

    # 批量提取模板 (利用缓存)
    template_strs = extract_templates_batch(sentences)

    # 构建模板列表
    templates = []
    for i, (sent, template) in enumerate(zip(sentences, template_strs)):
        templates.append({
            "text": sent,
            "template": template,
            "position": i,
            "is_opening": i < 3,
            "is_ending": i >= len(sentences) - 3 if len(sentences) > 3 else False
        })

    # 分析开场类型
    opening_type = None
    if sentences:
        opening_type = analyze_opening_type(sentences[0])

    # 统计情感词汇
    emotion_stats = {}
    for emotion, config in EMOTION_VOCABULARY.items():
        count = 0
        found_expressions = []
        for expr in config["expressions"]:
            expr_count = content.count(expr)
            if expr_count > 0:
                count += expr_count
                found_expressions.append({"expr": expr, "count": expr_count})
        if count > 0:
            emotion_stats[emotion] = {
                "total": count,
                "expressions": found_expressions
            }

    return {
        "chapter_id": chapter_id,
        "chapter_number": chapter_number,
        "chapter_title": title,
        "templates": templates,
        "sentence_count": len(sentences),
        "opening_type": opening_type,
        "emotion_stats": emotion_stats
    }


async def get_or_create_chapter_cache(
    db: AsyncSession,
    chapter: Chapter,
    force_refresh: bool = False
) -> Dict:
    """获取或创建章节分析缓存

    Args:
        db: 数据库会话
        chapter: 章节对象
        force_refresh: 是否强制刷新

    Returns:
        章节分析结果
    """
    content = chapter.content or ""
    content_hash = compute_content_hash(content)

    # 查询现有缓存
    if not force_refresh:
        result = await db.execute(
            select(ChapterPatternCache).where(
                ChapterPatternCache.chapter_id == chapter.id
            )
        )
        cache = result.scalars().first()

        # 缓存有效：哈希匹配且版本一致
        if cache and cache.content_hash == content_hash and cache.analysis_version == ANALYSIS_VERSION:
            logger.debug(f"使用缓存: 章节 {chapter.chapter_number}")
            return {
                "chapter_id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "chapter_title": chapter.title,
                "templates": cache.templates,
                "sentence_count": cache.sentence_count,
                "opening_type": cache.opening_type,
                "emotion_stats": cache.emotion_stats or {}
            }

    # 需要重新分析
    logger.debug(f"重新分析: 章节 {chapter.chapter_number}")
    analysis = analyze_single_chapter(
        chapter.id,
        chapter.chapter_number,
        content,
        chapter.title
    )

    # 更新或创建缓存
    result = await db.execute(
        select(ChapterPatternCache).where(
            ChapterPatternCache.chapter_id == chapter.id
        )
    )
    cache = result.scalars().first()

    if cache:
        cache.content_hash = content_hash
        cache.chapter_number = chapter.chapter_number
        cache.templates = analysis["templates"]
        cache.sentence_count = analysis["sentence_count"]
        cache.opening_type = analysis["opening_type"]
        cache.emotion_stats = analysis["emotion_stats"]
        cache.analysis_version = ANALYSIS_VERSION
    else:
        cache = ChapterPatternCache(
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            chapter_number=chapter.chapter_number,
            content_hash=content_hash,
            templates=analysis["templates"],
            sentence_count=analysis["sentence_count"],
            opening_type=analysis["opening_type"],
            emotion_stats=analysis["emotion_stats"],
            analysis_version=ANALYSIS_VERSION
        )
        db.add(cache)

    return analysis


async def analyze_project_patterns_incremental(
    db: AsyncSession,
    project_id: str,
    min_chapters: int = 5,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """增量分析项目的套路化程度

    核心逻辑:
    1. 检查每个章节的内容哈希是否变化
    2. 只重新分析变化的章节
    3. 使用缓存的章节数据进行聚合

    Args:
        db: 数据库会话
        project_id: 项目ID
        min_chapters: 最少需要的章节数
        force_refresh: 强制刷新所有缓存

    Returns:
        分析结果
    """
    # 1. 获取所有章节
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    if len(chapters) < min_chapters:
        return {
            "status": "insufficient_data",
            "message": f"需要至少{min_chapters}个章节才能进行套路化分析",
            "current_chapters": len(chapters)
        }

    logger.info(f"开始增量分析项目 {project_id}，共 {len(chapters)} 章")

    # 2. 获取或创建每个章节的缓存
    chapter_analyses = []
    cached_count = 0
    refreshed_count = 0

    for i, chapter in enumerate(chapters):
        if not chapter.content:
            continue

        # 检查是否需要刷新
        content_hash = compute_content_hash(chapter.content)

        if not force_refresh:
            cache_result = await db.execute(
                select(ChapterPatternCache).where(
                    ChapterPatternCache.chapter_id == chapter.id
                )
            )
            cache = cache_result.scalars().first()

            if cache and cache.content_hash == content_hash and cache.analysis_version == ANALYSIS_VERSION:
                # 使用缓存
                chapter_analyses.append({
                    "chapter_id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "chapter_title": chapter.title,
                    "templates": cache.templates,
                    "sentence_count": cache.sentence_count,
                    "opening_type": cache.opening_type,
                    "emotion_stats": cache.emotion_stats or {}
                })
                cached_count += 1
                continue

        # 需要重新分析
        analysis = await get_or_create_chapter_cache(db, chapter, force_refresh=True)
        chapter_analyses.append(analysis)
        refreshed_count += 1

        # 每处理 5 章输出一次进度
        if refreshed_count % 5 == 0:
            logger.info(f"[增量分析] 已分析 {refreshed_count} 章")

    logger.info(f"[增量分析] 完成: 缓存命中 {cached_count} 章, 重新分析 {refreshed_count} 章")

    if not chapter_analyses:
        return {
            "status": "no_content",
            "message": "章节内容为空"
        }

    # 3. 聚合所有章节的数据
    all_templates = []
    chapters_content = []
    all_sentences = []

    for ca in chapter_analyses:
        # 收集模板
        for t in ca["templates"]:
            all_templates.append({
                **t,
                "chapter_id": ca["chapter_id"],
                "chapter_number": ca["chapter_number"],
                "chapter_title": ca.get("chapter_title", "")
            })

        # 收集句子（用于开场分析）
        for t in ca["templates"]:
            all_sentences.append({
                "text": t["text"],
                "chapter_id": ca["chapter_id"],
                "chapter_number": ca["chapter_number"],
                "position": t["position"],
                "is_opening": t["is_opening"],
                "is_ending": t["is_ending"]
            })

    total_sentences = sum(ca["sentence_count"] for ca in chapter_analyses)
    logger.info(f"[增量分析] 聚合完成: {len(chapters)} 章, {total_sentences} 句")

    # 4. 聚类分析
    logger.info("[增量分析] 开始模板聚类...")
    clusters = cluster_templates(all_templates)
    logger.info(f"[增量分析] 聚类完成，共 {len(clusters)} 个簇")

    # 5. 找出重复模式
    patterns = []
    for cluster in clusters:
        if len(cluster) >= 3:
            chapter_numbers = list(set(c["chapter_number"] for c in cluster))
            chapter_numbers.sort()

            patterns.append({
                "template": cluster[0]["template"],
                "count": len(cluster),
                "examples": [c["text"] for c in cluster[:5]],
                "chapters": chapter_numbers,
                "is_opening_pattern": all(c["is_opening"] for c in cluster),
                "is_ending_pattern": all(c["is_ending"] for c in cluster)
            })

    patterns.sort(key=lambda x: x["count"], reverse=True)
    logger.info(f"[增量分析] 发现 {len(patterns)} 个重复模式")

    # 6. 分析开场模式
    opening_analysis = analyze_openings(all_sentences, len(chapters))

    # 7. 聚合情感词汇统计
    emotion_diversity = aggregate_emotion_stats(chapter_analyses)

    # 8. N-gram 分析
    ngram_analysis = analyze_ngram_patterns(all_templates)

    # 9. 计算评分
    score = calculate_pattern_score(
        patterns, opening_analysis, emotion_diversity,
        len(chapters), ngram_analysis
    )
    level = get_pattern_level(score)

    # 10. 生成建议
    suggestions = generate_pattern_suggestions(
        patterns, opening_analysis, emotion_diversity, ngram_analysis
    )

    # 11. 构建结果
    analysis_result = {
        "status": "success",
        "score": score,
        "level": level,
        "chapters_analyzed": len(chapters),
        "patterns_found": len(patterns),
        "top_patterns": patterns[:10],
        "opening_analysis": opening_analysis,
        "emotion_diversity": emotion_diversity,
        "ngram_analysis": ngram_analysis,
        "suggestions": suggestions,
        "incremental_stats": {
            "cached_chapters": cached_count,
            "refreshed_chapters": refreshed_count
        }
    }

    # 12. 保存分析结果
    await save_pattern_analysis(db, project_id, analysis_result)
    await db.commit()

    logger.info(f"项目 {project_id} 增量分析完成: score={score}, patterns={len(patterns)}")

    return analysis_result


def aggregate_emotion_stats(chapter_analyses: List[Dict]) -> Dict:
    """聚合所有章节的情感统计"""
    emotion_counts = {emotion: Counter() for emotion in EMOTION_VOCABULARY.keys()}

    for ca in chapter_analyses:
        for emotion, stats in ca.get("emotion_stats", {}).items():
            for expr_data in stats.get("expressions", []):
                emotion_counts[emotion][expr_data["expr"]] += expr_data["count"]

    # 使用现有的分析逻辑
    result = {}
    total_expressions = 0
    total_unique = 0

    for emotion, counter in emotion_counts.items():
        if counter:
            expressions = counter.most_common(10)
            total = sum(counter.values())
            unique = len(counter)

            top_expr = expressions[0] if expressions else (None, 0)
            concentration = top_expr[1] / total if total > 0 else 0

            result[emotion] = {
                "expressions": expressions,
                "total_count": total,
                "unique_count": unique,
                "concentration": round(concentration, 2),
                "top_expression": top_expr[0],
                "top_count": top_expr[1]
            }

            total_expressions += total
            total_unique += unique

    # 计算多样性评分
    if total_expressions == 0:
        diversity_score = 50
    elif total_expressions < 10:
        diversity_score = 60
    else:
        diversity_ratio = total_unique / total_expressions
        base_score = int(diversity_ratio * 200)
        quantity_bonus = min(30, total_unique * 3)
        diversity_score = min(100, base_score + quantity_bonus)

    # 找出最单一的情感
    most_concentrated = None
    max_concentration = 0
    for emotion, data in result.items():
        if data["concentration"] > max_concentration and data["total_count"] >= 5:
            max_concentration = data["concentration"]
            most_concentrated = emotion

    suggestion = ""
    if most_concentrated and max_concentration > 0.7:
        emotion_names = {
            "happy": "开心", "sad": "悲伤", "angry": "愤怒",
            "fear": "恐惧", "surprise": "惊讶"
        }
        top_expr = result[most_concentrated]["top_expression"]
        suggestion = f"表达「{emotion_names.get(most_concentrated, most_concentrated)}」时，{int(max_concentration * 100)}%使用「{top_expr}」，建议扩展情感表达词汇"

    return {
        "emotions": result,
        "diversity_score": diversity_score,
        "total_expressions": total_expressions,
        "total_unique": total_unique,
        "most_concentrated_emotion": most_concentrated,
        "suggestion": suggestion
    }


async def clear_project_pattern_cache(db: AsyncSession, project_id: str):
    """清除项目的所有章节分析缓存"""
    await db.execute(
        delete(ChapterPatternCache).where(
            ChapterPatternCache.project_id == project_id
        )
    )
    await db.commit()
    logger.info(f"已清除项目 {project_id} 的套路化分析缓存")
