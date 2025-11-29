"""
词条数据模型 - 存储用户自定义的百科词条
"""
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid

class Term(Base):
    """词条模型 - 用户定义的专有名词、设定等"""
    __tablename__ = "terms"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属项目ID")
    
    name = Column(String(200), nullable=False, comment="词条名称（用于高亮匹配）", index=True)
    description = Column(Text, nullable=True, comment="词条详细描述")
    
    created_by = Column(String(100), ForeignKey("users.user_id"), nullable=True, comment="创建者ID")
    created_at = Column(Text, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<Term(id={self.id}, name={self.name}, project_id={self.project_id})>"

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at
        }
