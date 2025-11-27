"""新功能服务层 - 设定追溯与矛盾检测、思维链图谱"""
from .entity_extractor import EntityExtractor, EntityInfo, chinese_to_number, normalize_age_value
from .conflict_detector import ConflictDetector, ConflictDetail, semantic_similarity, extract_number
from .link_analyzer import LinkAnalyzer, LinkAnalysis, LINK_TYPES

__all__ = [
    # 实体提取
    "EntityExtractor",
    "EntityInfo",
    "chinese_to_number",
    "normalize_age_value",
    # 矛盾检测
    "ConflictDetector",
    "ConflictDetail",
    "semantic_similarity",
    "extract_number",
    # 章节关系分析
    "LinkAnalyzer",
    "LinkAnalysis",
    "LINK_TYPES",
]
