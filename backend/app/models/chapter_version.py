"""章节版本历史模型 - 轻量级版本控制"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class ChapterVersion(Base):
    """章节版本历史表"""
    __tablename__ = "chapter_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)

    # 内容（备份所有内容字段）
    title = Column(String(200), nullable=False, comment="章节标题")
    content = Column(Text, nullable=False, comment="章节正文")
    summary = Column(Text, comment="章节摘要")
    word_count = Column(Integer, default=0, comment="字数统计")
    status = Column(String(20), default="draft", comment="章节状态")

    # 大纲关联（备份大纲结构）
    outline_id = Column(String(36), comment="关联的大纲ID")
    sub_index = Column(Integer, default=1, comment="大纲下的子章节序号")

    # 大纲展开规划（备份AI规划）
    expansion_plan = Column(Text, comment="展开规划详情(JSON)")

    # 元数据
    version_number = Column(Integer, default=1, comment="版本号（第1版、第2版...）")
    source = Column(String(20), default="user", comment="user:手动编辑, ai:AI生成, mix:AI+手动修改, restore:版本恢复, snapshot:快照")

    # 谁、什么时候
    created_by = Column(String(100), ForeignKey("users.user_id"), nullable=True, comment="创建者ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # AI生成参数（记录生成信息）
    ai_provider = Column(String(50), nullable=True, comment="AI提供商")
    ai_model = Column(String(100), nullable=True, comment="AI模型")
    generation_prompt = Column(Text, nullable=True, comment="生成提示词（可选）")

    def __repr__(self):
        return f"<ChapterVersion(id={self.id}, chapter_id={self.chapter_id}, version={self.version_number}, source={self.source}, title={self.title})>"
