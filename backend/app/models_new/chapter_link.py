"""章节关系图谱模型"""
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Index, Integer
from sqlalchemy.sql import func
from app.database import Base
import uuid


class ChapterLink(Base):
    """章节关系链接表"""
    __tablename__ = "chapter_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")

    # 关系两端
    from_chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True, comment="源章节ID（埋下伏笔）")
    from_chapter_title = Column(String(200), comment="源章节标题（缓存）")
    to_chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True, comment="目标章节ID（回收伏笔）")
    to_chapter_title = Column(String(200), comment="目标章节标题（缓存）")

    # 关系类型
    link_type = Column(String(30), nullable=False, index=True, comment="关系类型: causality(因果)/foreshadowing(伏笔)/callback(回顾)/parallel(平行)/contrast(对比)/continuation(承上启下)")
    link_type_display = Column(String(50), comment="关系类型显示名称")

    # 关系描述
    description = Column(Text, comment="关系描述（AI生成的说明）")
    from_element = Column(Text, comment="源章节的关联元素（埋下什么）")
    to_element = Column(Text, comment="目标章节的关联元素（回收什么）")

    # 推理链条（思维链）
    reasoning_chain = Column(Text, comment="推理链条（JSON格式）")
    # 示例:
    # {
    #   "premise": "A章节埋下伏笔：小明收到神秘信件",
    #   "development": "B章节描写小明发现信件来自失踪的父亲",
    #   "conclusion": "C章节揭示父亲的真实身份"
    # }

    # 强度与重要性
    strength = Column(Float, default=0.5, comment="关系强度（0-1）")
    importance_score = Column(Float, comment="重要性评分（0-100）")

    # AI信息
    confidence = Column(Float, comment="AI识别置信度（0-1）")
    ai_model = Column(String(100), comment="使用的AI模型")

    # 元数据
    is_confirmed = Column(String(1), default="N", comment="是否人工确认: Y/N")
    time_gap = Column(Integer, comment="时间间隔（章节序号差）")
    tags = Column(Text, comment="标签（JSON列表）")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        Index('idx_chapter_relation', 'from_chapter_id', 'to_chapter_id'),  # 一对多关系索引
        Index('idx_link_type_filter', 'link_type'),
        Index('idx_importance_sort', 'importance_score'),
    )

    def __repr__(self):
        return f"<ChapterLink(id={self.id}, from={self.from_chapter_title[:20]}, to={self.to_chapter_title[:20]}, type={self.link_type})>"
