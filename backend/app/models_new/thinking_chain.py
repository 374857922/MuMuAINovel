"""思维链详细记录模型"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Float
from sqlalchemy.sql import func
from app.database import Base
import uuid


class ThinkingChain(Base):
    """思维链详细记录表 - 存储AI推理过程"""
    __tablename__ = "thinking_chains"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), index=True, comment="关联章节ID（可选）")

    # 思维链类型
    chain_type = Column(String(30), nullable=False, index=True, comment="类型: generation(生成时)/analysis(分析时)/detection(检测时)")

    # 思维过程（JSON格式，包含多步推理）
    # 示例结构:
    # {
    #   "steps": [
    #     {
    #       "step": 1,
    #       "thought": "分析角色背景...",
    #       "reasoning": "因为角色A在第一章有XX经历...",
    #       "context": {"chapters": ["ch_1", "ch_3"]}
    #     },
    #     {
    #       "step": 2,
    #       "thought": "考虑情节冲突...",
    #       "reasoning": "与角色B的目标冲突...",
    #       "context": {"relationships": ["rel_1"]}
    #     }
    #   ],
    #   "conclusion": "因此角色A应该做出XX行动"
    # }
    reasoning_steps = Column(Text, nullable=False, comment="推理步骤（JSON数组）")
    conclusion = Column(Text, comment="最终结论")
    supporting_evidence = Column(Text, comment="支持证据（JSON数组，引用快照ID）")

    # 关联的快照
    snapshot_ids = Column(Text, comment="关联的EntitySnapshot ID列表（JSON）")
    conflict_ids = Column(Text, comment="关联的Conflict ID列表（JSON）")
    link_ids = Column(Text, comment="关联的ChapterLink ID列表（JSON）")

    # AI信息
    ai_model = Column(String(100), comment="使用的AI模型")
    temperature = Column(Float, comment="AI温度参数")
    prompt_tokens = Column(Integer, default=0, comment="输入token数")
    completion_tokens = Column(Integer, default=0, comment="输出token数")

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<ThinkingChain(id={self.id[:8]}, type={self.chain_type})>"
