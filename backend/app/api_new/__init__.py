"""新功能API路由 - 设定追溯与矛盾检测、思维链图谱"""
from fastapi import APIRouter
from . import conflicts, chapter_graph

# 创建主路由
router = APIRouter()

# 注册子路由
router.include_router(conflicts.router)
router.include_router(chapter_graph.router)

# 导出给主应用使用
__all__ = ["router"]
