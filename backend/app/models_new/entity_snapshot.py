"""实体快照模型 - 记录每个设定点的快照，用于追溯和矛盾检测"""
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class EntitySnapshot(Base):
    """实体快照表 - 记录每个设定点的快照"""
    __tablename__ = "entity_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")

    # 实体信息
    entity_type = Column(String(30), nullable=False, index=True, comment="实体类型: character/location/item/rule")
    entity_id = Column(String(36), nullable=False, index=True, comment="实体ID（角色ID/地点ID等）")
    entity_name = Column(String(200), comment="实体名称（用于快速查询）")

    # 属性信息
    property_name = Column(String(100), nullable=False, index=True, comment="属性名: age/location/ability/status")
    property_value = Column(Text, nullable=False, comment="属性值（JSON格式或纯文本）")
    property_type = Column(String(30), comment="属性类型: string/number/boolean/list")
    
    # 属性层级 (新算法核心)
    layer = Column(String(50), default="Intrinsic", comment="属性层级: Intrinsic(固有)/Appearance(表象)/Evaluation(评价)")
    source_type = Column(String(50), default="Narrator", comment="来源类型: Narrator(旁白)/Character(角色)")

    # 来源信息（用于追溯）
    source_chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), comment="来源章节ID")
    source_outline_id = Column(String(36), ForeignKey("outlines.id", ondelete="SET NULL"), comment="来源大纲ID")
    source_quote = Column(Text, comment="原始文本引用（提取该设定的原文）")
    source_context = Column(Text, comment="上下文信息")

    # AI识别信息
    confidence = Column(Float, default=0.8, comment="AI识别置信度（0-1）")
    ai_model = Column(String(100), comment="使用的AI模型")
    extraction_version = Column(String(20), comment="提取算法版本号")

    # 元数据
    is_confirmed = Column(String(1), default="N", comment="是否人工确认: Y/N")
    tags = Column(Text, comment="标签（JSON列表）")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 索引优化
    __table_args__ = (
        Index('idx_entity_lookup', 'project_id', 'entity_id', 'property_name'),
        Index('idx_confidence_filter', 'confidence'),
    )

    def __repr__(self):
        return f"<EntitySnapshot(id={self.id}, entity={self.entity_name}, prop={self.property_name})>"
