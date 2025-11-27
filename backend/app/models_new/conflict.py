"""矛盾检测结果模型"""
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Conflict(Base):
    """矛盾检测结果表"""
    __tablename__ = "conflicts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")

    # 涉及实体
    entity_type = Column(String(30), nullable=False, comment="实体类型")
    entity_id = Column(String(36), nullable=False, index=True, comment="实体ID")
    entity_name = Column(String(200), comment="实体名称")

    # 矛盾的属性
    property_name = Column(String(100), nullable=False, comment="属性名")
    property_display = Column(String(200), comment="属性显示名称（如：年龄/位置/能力）")

    # 两个冲突的快照
    snapshot_a_id = Column(String(36), ForeignKey("entity_snapshots.id"), nullable=False, comment="第一个快照ID")
    snapshot_a_value = Column(Text, comment="快照A的属性值")
    snapshot_a_source = Column(String(36), comment="快照A的章节ID")

    snapshot_b_id = Column(String(36), ForeignKey("entity_snapshots.id"), nullable=False, comment="第二个快照ID")
    snapshot_b_value = Column(Text, comment="快照B的属性值")
    snapshot_b_source = Column(String(36), comment="快照B的章节ID")

    # 矛盾信息
    conflict_type = Column(String(30), comment="矛盾类型: contradiction(直接矛盾)/inconsistency(不一致)/ambiguity(模糊不清)")
    severity = Column(String(20), default="warning", comment="严重程度: critical/warning/info")
    description = Column(Text, comment="矛盾描述（AI生成的说明）")

    # 处理状态
    status = Column(String(20), default="detected", comment="状态: detected(已检测)/verified(已确认)/resolved(已解决)/ignored(已忽略)")
    resolution = Column(Text, comment="解决方案说明")
    resolved_by = Column(String(36), comment="解决人ID")
    resolved_at = Column(DateTime, comment="解决时间")

    # AI信息
    confidence = Column(Float, comment="矛盾检测置信度")
    ai_suggestion = Column(Text, comment="AI建议的解决方案")

    created_at = Column(DateTime, server_default=func.now(), comment="检测时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        Index('idx_entity_conflict', 'entity_id', 'property_name'),
        Index('idx_status_filter', 'status'),
    )

    def __repr__(self):
        return f"<Conflict(id={self.id}, entity={self.entity_name}, prop={self.property_name})>"
