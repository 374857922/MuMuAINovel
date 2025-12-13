"""
AI腔调词汇库模型 - 存储AI常用词汇和替换建议
"""
from sqlalchemy import Column, String, Text, Integer, Float, JSON
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AIVocabulary(Base):
    """AI腔调词汇库 - 存储AI常用词汇及其替换建议"""
    __tablename__ = "ai_vocabulary"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 词汇信息
    word = Column(String(100), nullable=False, unique=True, index=True, comment="AI腔调词汇")
    category = Column(String(20), nullable=False, index=True, comment="分类: critical/warning/emotional/scene/transition")
    severity = Column(String(10), nullable=False, index=True, comment="严重程度: high/medium/low")

    # 替换建议 (JSON数组)
    alternatives = Column(JSON, nullable=True, comment="替换建议列表")

    # 说明
    description = Column(Text, nullable=True, comment="为什么这是AI腔调的说明")

    # 统计
    usage_count = Column(Integer, default=0, comment="被检测到的次数")

    # 是否为系统预置（用户不能删除）
    is_system = Column(Integer, default=1, comment="是否系统预置: 1=是, 0=用户自定义")

    # 时间
    created_at = Column(Text, server_default=func.now(), comment="创建时间")
    updated_at = Column(Text, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<AIVocabulary(word={self.word}, category={self.category}, severity={self.severity})>"

    def to_dict(self):
        return {
            "id": self.id,
            "word": self.word,
            "category": self.category,
            "severity": self.severity,
            "alternatives": self.alternatives or [],
            "description": self.description,
            "usage_count": self.usage_count,
            "is_system": self.is_system,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class ChapterToneAnalysis(Base):
    """章节文风检测结果 - 存储单章节的AI腔调检测结果"""
    __tablename__ = "chapter_tone_analysis"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联
    project_id = Column(String(36), nullable=False, index=True, comment="项目ID")
    chapter_id = Column(String(36), nullable=False, unique=True, index=True, comment="章节ID")

    # 检测结果
    score = Column(Integer, nullable=False, comment="自然度评分 0-100")
    level = Column(String(20), nullable=False, comment="评级: 自然/一般/明显/严重")
    issue_count = Column(Integer, nullable=False, default=0, comment="问题数量")

    # 详细问题列表 (JSON)
    issues = Column(JSON, nullable=False, comment="问题列表")

    # 统计指标
    word_count = Column(Integer, nullable=True, comment="总字数")
    sentence_count = Column(Integer, nullable=True, comment="句子数量")
    avg_sentence_length = Column(Float, nullable=True, comment="平均句子长度")
    sentence_length_std = Column(Float, nullable=True, comment="句子长度标准差")

    # 元数据
    detection_version = Column(String(10), default="1.0", comment="检测算法版本")
    created_at = Column(Text, server_default=func.now(), comment="检测时间")

    def __repr__(self):
        return f"<ChapterToneAnalysis(chapter_id={self.chapter_id}, score={self.score}, level={self.level})>"

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "chapter_id": self.chapter_id,
            "score": self.score,
            "level": self.level,
            "issue_count": self.issue_count,
            "issues": self.issues or [],
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "avg_sentence_length": self.avg_sentence_length,
            "sentence_length_std": self.sentence_length_std,
            "detection_version": self.detection_version,
            "created_at": self.created_at
        }


class ProjectPatternAnalysis(Base):
    """项目套路化分析结果 - 存储跨章节的套路化检测结果"""
    __tablename__ = "project_pattern_analysis"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联
    project_id = Column(String(36), nullable=False, unique=True, index=True, comment="项目ID")

    # 检测结果
    score = Column(Integer, nullable=False, comment="多样性评分 0-100")
    level = Column(String(20), nullable=False, comment="评级")
    chapters_analyzed = Column(Integer, nullable=False, comment="分析的章节数")
    patterns_found = Column(Integer, nullable=False, comment="发现的重复模式数")

    # 详细分析 (JSON)
    top_patterns = Column(JSON, nullable=False, comment="前10个高频模式")
    opening_analysis = Column(JSON, nullable=False, comment="开场模式分析")
    emotion_diversity = Column(JSON, nullable=False, comment="情感词汇多样性")
    ngram_analysis = Column(JSON, nullable=True, comment="N-gram叙事结构分析")  # 新增
    suggestions = Column(JSON, nullable=False, comment="改进建议")

    # 元数据
    detection_version = Column(String(10), default="2.0", comment="检测算法版本")
    created_at = Column(Text, server_default=func.now(), comment="检测时间")

    def __repr__(self):
        return f"<ProjectPatternAnalysis(project_id={self.project_id}, score={self.score})>"

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "score": self.score,
            "level": self.level,
            "chapters_analyzed": self.chapters_analyzed,
            "patterns_found": self.patterns_found,
            "top_patterns": self.top_patterns or [],
            "opening_analysis": self.opening_analysis or {},
            "emotion_diversity": self.emotion_diversity or {},
            "ngram_analysis": self.ngram_analysis or {},  # 新增
            "suggestions": self.suggestions or [],
            "detection_version": self.detection_version,
            "created_at": self.created_at
        }


class RewriteRecord(Base):
    """改写记录 - 存储文本改写历史"""
    __tablename__ = "rewrite_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联
    project_id = Column(String(36), nullable=False, index=True, comment="项目ID")
    chapter_id = Column(String(36), nullable=True, index=True, comment="章节ID")

    # 改写内容
    original_text = Column(Text, nullable=False, comment="原始文本")
    rewritten_text = Column(Text, nullable=False, comment="改写后文本")
    rewrite_type = Column(String(20), nullable=False, comment="改写类型: replace/rewrite/restructure")

    # 触发来源
    trigger_type = Column(String(20), nullable=False, comment="触发类型: tone_analysis/pattern_analysis/manual")
    trigger_issue = Column(JSON, nullable=True, comment="触发的具体问题")

    # 用户操作
    status = Column(String(20), default="pending", index=True, comment="状态: pending/accepted/rejected")
    accepted_at = Column(Text, nullable=True, comment="采纳时间")

    # 元数据
    ai_model = Column(String(50), nullable=True, comment="使用的AI模型")
    created_at = Column(Text, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<RewriteRecord(id={self.id}, rewrite_type={self.rewrite_type}, status={self.status})>"

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "chapter_id": self.chapter_id,
            "original_text": self.original_text,
            "rewritten_text": self.rewritten_text,
            "rewrite_type": self.rewrite_type,
            "trigger_type": self.trigger_type,
            "trigger_issue": self.trigger_issue,
            "status": self.status,
            "accepted_at": self.accepted_at,
            "ai_model": self.ai_model,
            "created_at": self.created_at
        }


class ChapterPatternCache(Base):
    """章节套路化分析缓存 - 用于增量分析"""
    __tablename__ = "chapter_pattern_cache"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联
    project_id = Column(String(36), nullable=False, index=True, comment="项目ID")
    chapter_id = Column(String(36), nullable=False, unique=True, index=True, comment="章节ID")
    chapter_number = Column(Integer, nullable=False, comment="章节序号")

    # 内容指纹 (用于检测变化)
    content_hash = Column(String(64), nullable=False, comment="内容MD5哈希")

    # 缓存的分析数据 (JSON)
    templates = Column(JSON, nullable=False, comment="句子模板列表")
    sentence_count = Column(Integer, nullable=False, comment="句子数量")
    opening_type = Column(String(20), nullable=True, comment="开场类型")
    emotion_stats = Column(JSON, nullable=True, comment="情感词汇统计")

    # 元数据
    analysis_version = Column(String(10), default="2.0", comment="分析算法版本")
    created_at = Column(Text, server_default=func.now(), comment="创建时间")
    updated_at = Column(Text, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<ChapterPatternCache(chapter_id={self.chapter_id}, sentences={self.sentence_count})>"

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "chapter_id": self.chapter_id,
            "chapter_number": self.chapter_number,
            "content_hash": self.content_hash,
            "templates": self.templates or [],
            "sentence_count": self.sentence_count,
            "opening_type": self.opening_type,
            "emotion_stats": self.emotion_stats or {},
            "analysis_version": self.analysis_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
