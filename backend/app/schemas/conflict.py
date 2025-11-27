"""矛盾检测相关的 Pydantic Schema"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ConflictResponse(BaseModel):
    """矛盾响应模型"""
    id: str
    entityId: str
    entityName: Optional[str] = None
    property: str
    valueA: str
    valueB: str
    severity: str
    status: str
    description: Optional[str] = None
    aiSuggestion: Optional[str] = None


class ConflictDetailResponse(BaseModel):
    """矛盾详情响应模型"""
    id: str
    entity: dict
    property: dict
    snapshotA: dict
    snapshotB: dict
    conflict: dict
    aiSuggestion: Optional[str] = None

    class Config:
        populate_by_name = True


class ConflictListResponse(BaseModel):
    """矛盾列表响应模型"""
    total: int
    items: List[ConflictResponse]


class ConflictResolveRequest(BaseModel):
    """解决矛盾请求模型"""
    resolution: str = Field(..., min_length=1, max_length=1000, description="解决方案说明")


class EntitySnapshotResponse(BaseModel):
    """实体快照响应模型"""
    id: str
    value: str
    propertyType: Optional[str] = None
    sourceChapterId: Optional[str] = None
    quote: Optional[str] = None
    confidence: float = 0.8
    createdAt: Optional[datetime] = None

    class Config:
        populate_by_name = True


class PropertySnapshotsResponse(BaseModel):
    """属性快照列表响应"""
    propertyName: str
    displayName: str
    snapshots: List[EntitySnapshotResponse]
    hasConflict: bool = False
    conflictStatus: str = "none"


class EntitySnapshotsResponse(BaseModel):
    """实体设定快照响应"""
    entityId: str
    entityName: str
    entityType: str
    properties: List[PropertySnapshotsResponse]
