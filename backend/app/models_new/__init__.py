"""新功能数据模型 - 设定追溯与矛盾检测、思维链图谱"""
from .entity_snapshot import EntitySnapshot
from .conflict import Conflict
from .chapter_link import ChapterLink
from .thinking_chain import ThinkingChain

__all__ = [
    "EntitySnapshot",      # 实体快照
    "Conflict",             # 矛盾检测
    "ChapterLink",          # 章节关系
    "ThinkingChain",        # 思维链
]
