"""矛盾检测服务 - 精准检测设定冲突"""
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models_new import EntitySnapshot, Conflict
from app.models.chapter import Chapter
from app.services.ai_service import AIService
from app.logger import get_logger

logger = get_logger(__name__)

# 中文数字映射
CN_NUM_MAP = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '百': 100, '千': 1000, '万': 10000
}


def chinese_to_number(cn_str: str) -> Optional[int]:
    """将中文数字转换为阿拉伯数字"""
    if not cn_str:
        return None
    try:
        return int(cn_str)
    except ValueError:
        pass
    
    result = 0
    temp = 0
    for char in cn_str:
        if char in CN_NUM_MAP:
            num = CN_NUM_MAP[char]
            if num >= 10:
                if temp == 0:
                    temp = 1
                temp *= num
                if num == 10:
                    result += temp
                    temp = 0
            else:
                temp = num
        else:
            break
    result += temp
    return result if result > 0 else None


def extract_number(value: str) -> Optional[float]:
    """从字符串中提取数字"""
    if not value:
        return None
    
    try:
        return float(value)
    except ValueError:
        pass
    
    num_match = re.search(r'(\d+\.?\d*)', str(value))
    if num_match:
        return float(num_match.group(1))
    
    cn_match = re.search(r'([零一二两三四五六七八九十百千万]+)', str(value))
    if cn_match:
        num = chinese_to_number(cn_match.group(1))
        if num:
            return float(num)
    
    return None


def normalize_text(text: str) -> str:
    """标准化文本用于比较"""
    if not text:
        return ""
    # 移除标点、空格，转小写
    return re.sub(r'[\s，。！？、（）()""\'\'：:；;～~]+', '', str(text).lower().strip())


def semantic_similarity(str1: str, str2: str) -> float:
    """计算语义相似度"""
    if not str1 or not str2:
        return 0.0
    
    clean1 = normalize_text(str1)
    clean2 = normalize_text(str2)
    
    if clean1 == clean2:
        return 1.0
    
    # 包含关系也视为高相似
    if clean1 in clean2 or clean2 in clean1:
        return 0.9
    
    return SequenceMatcher(None, clean1, clean2).ratio()


@dataclass
class ConflictDetail:
    """矛盾详情"""
    entity_id: str
    entity_name: str
    property_name: str
    value_a: str
    value_b: str
    source_a: str
    source_b: str
    severity: str
    description: str


class ConflictDetector:
    """精准矛盾检测器 - 只报告真正的矛盾"""

    # 只检测这些关键属性的矛盾（其他属性太主观，容易误报）
    CHECKABLE_PROPS = {
        # 身份类 - 通常不会变
        "gender", "性别",
        "species", "种族", "race",
        "bloodline", "血统",
        # 数值类 - 可以精确比较
        "age", "年龄",
        "height", "身高",
        "weight", "体重",
        # 明确的身份
        "identity", "身份",
        "title", "称号",
        "faction", "势力", "门派",
    }
    
    # 互斥值对（如果两个值在同一对中，则是矛盾）
    MUTUALLY_EXCLUSIVE = [
        # 性别
        ({"男", "男性", "男人", "男子", "他"}, {"女", "女性", "女人", "女子", "她"}),
        # 生死
        ({"死", "死亡", "已死", "死了", "去世"}, {"活", "活着", "存活", "生还"}),
        # 阵营
        ({"正派", "正道", "正义"}, {"邪派", "邪道", "邪恶", "魔道"}),
        ({"敌人", "敌方", "对手"}, {"朋友", "友方", "盟友", "伙伴"}),
    ]
    
    # 完全忽略的属性（太主观或经常变化）
    IGNORE_PROPS = {
        "description", "描述", "简介",
        "personality", "性格", "特点",
        "appearance", "外貌", "长相", "容貌",
        "ability", "能力", "技能", "skill",
        "status", "状态", "location", "位置",
        "mood", "心情", "emotion", "情绪",
        "thought", "想法", "attitude", "态度",
    }

    def __init__(self, ai_service: AIService = None):
        self.ai_service = ai_service
        # 提高置信度阈值，只检测高置信度的设定
        self.min_confidence = 0.75
        self._chapter_order_cache: Dict[str, int] = {}

    async def detect_all(self, project_id: str, db: AsyncSession) -> List[Conflict]:
        """检测项目中的真正矛盾"""
        # 只获取高置信度的快照
        result = await db.execute(
            select(EntitySnapshot).where(
                EntitySnapshot.project_id == project_id,
                EntitySnapshot.confidence >= self.min_confidence
            ).order_by(EntitySnapshot.entity_id, EntitySnapshot.property_name)
        )
        snapshots = result.scalars().all()

        logger.info(f"开始精准矛盾检测: project_id={project_id}, 高置信度快照={len(snapshots)}")

        # 按实体+属性分组
        snapshot_groups: Dict[str, List[EntitySnapshot]] = {}
        for snapshot in snapshots:
            prop_lower = snapshot.property_name.lower()
            
            # 跳过忽略的属性
            if any(ig in prop_lower for ig in self.IGNORE_PROPS):
                continue
            
            # 只检测可检查的属性
            if not any(cp in prop_lower for cp in self.CHECKABLE_PROPS):
                continue
                
            key = f"{snapshot.entity_id}:{snapshot.property_name}"
            if key not in snapshot_groups:
                snapshot_groups[key] = []
            snapshot_groups[key].append(snapshot)

        # 检测矛盾
        conflicts = []
        for key, group_snapshots in snapshot_groups.items():
            if len(group_snapshots) < 2:
                continue

            group_conflicts = await self._detect_in_group(group_snapshots, project_id, db)
            conflicts.extend(group_conflicts)

        logger.info(f"精准检测完成: 发现 {len(conflicts)} 个真正的矛盾")
        return conflicts

    async def _detect_in_group(
        self,
        snapshots: List[EntitySnapshot],
        project_id: str,
        db: AsyncSession
    ) -> List[Conflict]:
        """检测同一实体同一属性的矛盾"""
        conflicts = []
        property_name = snapshots[0].property_name.lower()

        # 按章节排序
        sorted_snapshots = []
        for s in snapshots:
            order = await self._get_chapter_order(s.source_chapter_id, db) if s.source_chapter_id else 0
            sorted_snapshots.append((order, s))
        sorted_snapshots.sort(key=lambda x: x[0])

        # 去重：合并完全相同的值
        unique_values: Dict[str, Tuple[int, EntitySnapshot]] = {}
        for order, snapshot in sorted_snapshots:
            norm_value = normalize_text(snapshot.property_value)
            if norm_value not in unique_values:
                unique_values[norm_value] = (order, snapshot)

        if len(unique_values) < 2:
            return conflicts

        # 比较不同的值
        values_list = list(unique_values.values())
        for i in range(len(values_list)):
            for j in range(i + 1, len(values_list)):
                order_a, snapshot_a = values_list[i]
                order_b, snapshot_b = values_list[j]
                
                conflict = await self._check_conflict(
                    snapshot_a, snapshot_b, 
                    order_a, order_b,
                    property_name, project_id, db
                )
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    async def _check_conflict(
        self,
        snapshot_a: EntitySnapshot,
        snapshot_b: EntitySnapshot,
        order_a: int,
        order_b: int,
        property_name: str,
        project_id: str,
        db: AsyncSession
    ) -> Optional[Conflict]:
        """精准判断两个值是否矛盾"""
        value_a = snapshot_a.property_value
        value_b = snapshot_b.property_value
        
        # 1. 高相似度 = 不矛盾（可能是同义表达）
        similarity = semantic_similarity(value_a, value_b)
        if similarity > 0.7:
            return None
        
        # 2. 检查是否为互斥值
        is_exclusive = self._check_mutually_exclusive(value_a, value_b)
        
        # 3. 数值类属性特殊处理
        if self._is_numeric_property(property_name):
            num_a = extract_number(value_a)
            num_b = extract_number(value_b)
            
            if num_a is not None and num_b is not None:
                # 年龄可以随时间增长
                if "age" in property_name or "年龄" in property_name:
                    if order_b > order_a and num_b >= num_a:
                        return None  # 合理的年龄增长
                    if order_a > order_b and num_a >= num_b:
                        return None
                    # 年龄倒退才是矛盾
                    if abs(num_a - num_b) <= 2:
                        return None  # 允许2岁误差
                else:
                    # 其他数值，允许10%误差
                    avg = (num_a + num_b) / 2
                    if avg > 0 and abs(num_a - num_b) / avg < 0.1:
                        return None
        
        # 4. 如果不是互斥值，且相似度在中等范围，可能只是不同描述
        if not is_exclusive and similarity > 0.4:
            return None
        
        # 5. 使用AI二次验证（如果可用）
        if self.ai_service and not is_exclusive:
            is_conflict, reason = await self._verify_with_ai(snapshot_a, snapshot_b, property_name)
            if not is_conflict:
                logger.debug(f"AI判定非矛盾: {snapshot_a.entity_name}.{property_name} - {reason}")
                return None
        
        # 6. 确认是矛盾，创建记录
        severity = "critical" if is_exclusive else "warning"
        
        description = f"【{snapshot_a.entity_name}】的{property_name}存在矛盾：「{value_a[:30]}」vs「{value_b[:30]}」"
        
        conflict = Conflict(
            project_id=project_id,
            entity_type=snapshot_a.entity_type,
            entity_id=snapshot_a.entity_id,
            entity_name=snapshot_a.entity_name,
            property_name=snapshot_a.property_name,
            property_display=property_name,
            snapshot_a_id=snapshot_a.id,
            snapshot_a_value=value_a,
            snapshot_a_source=snapshot_a.source_chapter_id,
            snapshot_b_id=snapshot_b.id,
            snapshot_b_value=value_b,
            snapshot_b_source=snapshot_b.source_chapter_id,
            conflict_type="contradiction" if is_exclusive else "inconsistency",
            severity=severity,
            description=description,
            confidence=min(snapshot_a.confidence, snapshot_b.confidence),
            ai_suggestion=self._generate_suggestion(property_name, value_a, value_b)
        )

        return conflict

    def _check_mutually_exclusive(self, value_a: str, value_b: str) -> bool:
        """检查两个值是否互斥"""
        norm_a = normalize_text(value_a)
        norm_b = normalize_text(value_b)
        
        for set_1, set_2 in self.MUTUALLY_EXCLUSIVE:
            a_in_1 = any(normalize_text(v) in norm_a or norm_a in normalize_text(v) for v in set_1)
            a_in_2 = any(normalize_text(v) in norm_a or norm_a in normalize_text(v) for v in set_2)
            b_in_1 = any(normalize_text(v) in norm_b or norm_b in normalize_text(v) for v in set_1)
            b_in_2 = any(normalize_text(v) in norm_b or norm_b in normalize_text(v) for v in set_2)
            
            # 一个在集合1，另一个在集合2 = 互斥
            if (a_in_1 and b_in_2) or (a_in_2 and b_in_1):
                return True
        
        return False

    def _is_numeric_property(self, property_name: str) -> bool:
        """判断是否为数值属性"""
        numeric_keywords = ["age", "年龄", "height", "身高", "weight", "体重", "level", "等级"]
        return any(k in property_name.lower() for k in numeric_keywords)

    async def _verify_with_ai(
        self,
        snapshot_a: EntitySnapshot,
        snapshot_b: EntitySnapshot,
        property_name: str
    ) -> Tuple[bool, str]:
        """使用AI验证是否真的矛盾"""
        try:
            prompt = f"""判断以下两个描述是否存在【真正的逻辑矛盾】。

角色/实体: {snapshot_a.entity_name}
属性: {property_name}
描述A: {snapshot_a.property_value}
描述B: {snapshot_b.property_value}

注意：
- 不同的描述方式不算矛盾（如"很高"和"身材高大"）
- 补充信息不算矛盾（如"会剑法"和"会刀法"）
- 随时间变化不算矛盾（如状态、位置、心情）
- 只有逻辑上不可能同时为真的才是矛盾（如"男"和"女"）

请只回答JSON：{{"is_conflict": true/false, "reason": "一句话说明"}}"""

            result = await self.ai_service.generate_text(prompt=prompt, temperature=0.1)
            
            content = result.get("content", "") if isinstance(result, dict) else str(result)
            
            try:
                data = json.loads(content)
            except:
                match = re.search(r'\{[^}]+\}', content)
                if match:
                    data = json.loads(match.group(0))
                else:
                    return True, "AI响应解析失败"
            
            return data.get("is_conflict", True), data.get("reason", "")
            
        except Exception as e:
            logger.error(f"AI验证失败: {str(e)}")
            return True, str(e)

    def _generate_suggestion(self, property_name: str, value_a: str, value_b: str) -> str:
        """生成解决建议"""
        if "性别" in property_name or "gender" in property_name.lower():
            return "请检查角色性别设定，确保前后一致"
        if "年龄" in property_name or "age" in property_name.lower():
            return "请确认角色年龄，注意时间线的推进"
        return f"请核实「{value_a[:20]}」和「{value_b[:20]}」哪个是正确的设定"

    def _get_property_display(self, property_name: str) -> str:
        """获取属性的显示名称"""
        display_map = {
            # 身份类
            "gender": "性别",
            "species": "种族",
            "race": "种族",
            "bloodline": "血统",
            "identity": "身份",
            "title": "称号",
            "faction": "势力",
            "sect": "门派",
            # 数值类
            "age": "年龄",
            "height": "身高",
            "weight": "体重",
            "level": "等级",
            "realm": "境界",
            "cultivation": "修为",
            # 描述类
            "name": "名称",
            "description": "描述",
            "personality": "性格",
            "appearance": "外貌",
            "ability": "能力",
            "skill": "技能",
            "talent": "天赋",
            "weakness": "弱点",
            # 状态类
            "status": "状态",
            "location": "位置",
            "mood": "心情",
            "emotion": "情绪",
            "thought": "想法",
            "attitude": "态度",
            # 关系类
            "relationship": "关系",
            "family": "家族",
            "master": "师父",
            "disciple": "徒弟",
            "lover": "恋人",
            "enemy": "仇人",
            "friend": "朋友",
            # 物品类
            "weapon": "武器",
            "equipment": "装备",
            "treasure": "宝物",
            "item": "物品",
        }
        return display_map.get(property_name.lower(), property_name)

    async def _get_chapter_order(self, chapter_id: str, db: AsyncSession) -> int:
        """获取章节顺序"""
        if not chapter_id:
            return 0
        if chapter_id in self._chapter_order_cache:
            return self._chapter_order_cache[chapter_id]
        
        result = await db.execute(
            select(Chapter.chapter_number).where(Chapter.id == chapter_id)
        )
        row = result.first()
        order = row[0] if row else 0
        self._chapter_order_cache[chapter_id] = order
        return order

    async def save_conflicts(self, conflicts: List[Conflict], db: AsyncSession) -> Tuple[int, List[str]]:
        """保存矛盾"""
        if not conflicts:
            return 0, []

        error_ids = []
        project_id = conflicts[0].project_id

        # 预加载已存在的矛盾
        existing_result = await db.execute(
            select(
                Conflict.entity_id,
                Conflict.property_name,
                Conflict.snapshot_a_id,
                Conflict.snapshot_b_id
            ).where(Conflict.project_id == project_id)
        )
        existing_keys = set()
        for row in existing_result.all():
            existing_keys.add(f"{row[0]}:{row[1]}:{row[2]}:{row[3]}")
            existing_keys.add(f"{row[0]}:{row[1]}:{row[3]}:{row[2]}")

        # 筛选新矛盾
        new_conflicts = []
        for conflict in conflicts:
            key = f"{conflict.entity_id}:{conflict.property_name}:{conflict.snapshot_a_id}:{conflict.snapshot_b_id}"
            if key not in existing_keys:
                new_conflicts.append(conflict)
                existing_keys.add(key)

        if new_conflicts:
            try:
                for c in new_conflicts:
                    db.add(c)
                await db.commit()
                logger.info(f"保存矛盾: {len(new_conflicts)} 条")
            except Exception as e:
                logger.error(f"保存失败: {str(e)}")
                await db.rollback()
                return 0, ["save_error"]

        return len(new_conflicts), error_ids

    async def get_conflicts_by_project(
        self,
        project_id: str,
        db: AsyncSession,
        severity: str = None,
        status: str = None
    ) -> List[Conflict]:
        """获取矛盾列表"""
        query = select(Conflict).where(Conflict.project_id == project_id)

        if severity:
            query = query.where(Conflict.severity == severity)
        if status:
            query = query.where(Conflict.status == status)

        query = query.order_by(Conflict.severity.desc(), Conflict.created_at.desc())

        result = await db.execute(query)
        return result.scalars().all()

    async def get_conflicts_by_entity(
        self,
        project_id: str,
        entity_id: str,
        db: AsyncSession
    ) -> List[Conflict]:
        """获取实体的矛盾"""
        result = await db.execute(
            select(Conflict).where(
                Conflict.project_id == project_id,
                Conflict.entity_id == entity_id
            ).order_by(Conflict.severity.desc())
        )
        return result.scalars().all()

    async def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        resolved_by: str,
        db: AsyncSession
    ) -> bool:
        """解决矛盾"""
        try:
            result = await db.execute(select(Conflict).where(Conflict.id == conflict_id))
            conflict = result.scalar_one_or_none()
            if not conflict:
                return False

            conflict.status = "resolved"
            conflict.resolution = resolution
            conflict.resolved_by = resolved_by
            conflict.resolved_at = datetime.now()
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"解决矛盾失败: {str(e)}")
            await db.rollback()
            return False

    async def ignore_conflict(self, conflict_id: str, db: AsyncSession) -> bool:
        """忽略矛盾"""
        try:
            result = await db.execute(select(Conflict).where(Conflict.id == conflict_id))
            conflict = result.scalar_one_or_none()
            if not conflict:
                return False

            conflict.status = "ignored"
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"忽略矛盾失败: {str(e)}")
            await db.rollback()
            return False

    def clear_cache(self):
        """清除缓存"""
        self._chapter_order_cache.clear()
