"""实体提取服务 - 从章节内容中提取角色/地点/物品的属性和设定"""
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models_new import EntitySnapshot
from app.models.chapter import Chapter
from app.models.character import Character
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
    
    # 先尝试直接转换阿拉伯数字
    try:
        return int(cn_str)
    except ValueError:
        pass
    
    # 处理中文数字
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


def normalize_age_value(age_str: str) -> Tuple[str, float]:
    """
    标准化年龄值，返回 (标准值, 置信度)
    支持: "20岁", "二十岁", "二十多岁", "约二十岁", "20出头"
    """
    age_str = age_str.strip()
    confidence = 0.8
    
    # 提取数字部分
    num_match = re.search(r'(\d+)', age_str)
    if num_match:
        return num_match.group(1), confidence
    
    # 处理中文数字
    cn_match = re.search(r'([零一二两三四五六七八九十百]+)', age_str)
    if cn_match:
        num = chinese_to_number(cn_match.group(1))
        if num:
            # 模糊描述降低置信度
            if any(w in age_str for w in ['多', '左右', '约', '大概', '出头', '不到']):
                confidence = 0.5
            return str(num), confidence
    
    return age_str, 0.3


@dataclass
class EntityInfo:
    """提取的实体信息"""
    entity_type: str  # character/location/item/rule
    entity_id: str
    entity_name: str
    property_name: str
    property_value: str
    property_type: str  # string/number/boolean/list
    quote: str  # 原文引用
    context: str  # 上下文
    confidence: float


class EntityExtractor:
    """实体提取器 - 从文本中提取设定信息"""

    def __init__(self, ai_service: AIService = None):
        """
        Args:
            ai_service: AI服务（可选，如果不传将使用规则匹配）
        """
        self.ai_service = ai_service
        self._character_cache: Dict[str, List[Character]] = {}

    async def _get_project_characters(self, project_id: str, db: AsyncSession) -> List[Character]:
        """获取项目的所有角色（带缓存）"""
        if project_id in self._character_cache:
            return self._character_cache[project_id]
        
        result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.is_organization == False
            )
        )
        characters = result.scalars().all()
        self._character_cache[project_id] = characters
        return characters

    def _find_matching_character(self, name: str, characters: List[Character]) -> Optional[Character]:
        """在已有角色中查找匹配的角色"""
        name = name.strip()
        for char in characters:
            # 精确匹配
            if char.name == name:
                return char
            # 部分匹配（名字包含或被包含）
            if len(name) >= 2 and (name in char.name or char.name in name):
                return char
        return None

    async def extract_from_chapter(
        self,
        chapter: Chapter,
        db: AsyncSession,
        ai_provider: str = None,
        ai_model: str = None
    ) -> List[EntitySnapshot]:
        """
        从单个章节提取所有实体快照

        Args:
            chapter: 章节对象
            db: 数据库会话
            ai_provider: AI提供商（openai/anthropic）
            ai_model: AI模型

        Returns:
            List[EntitySnapshot]: 提取的实体快照列表
        """
        if not chapter.content:
            return []

        # 获取项目已有角色用于关联
        characters = await self._get_project_characters(chapter.project_id, db)

        # 优先用AI提取
        if self.ai_service:
            snapshots = await self._extract_with_ai(chapter, characters, ai_provider, ai_model)
            if snapshots:
                return snapshots
        
        # 降级为规则匹配
        return await self._extract_with_rules(chapter, characters, db)

    async def _extract_with_ai(
        self,
        chapter: Chapter,
        characters: List[Character],
        ai_provider: str = None,
        ai_model: str = None
    ) -> List[EntitySnapshot]:
        """使用AI提取实体"""
        # 构建已有角色列表供AI参考
        char_names = [c.name for c in characters]
        char_list_str = "、".join(char_names) if char_names else "（暂无已定义角色）"

        prompt = f"""分析以下小说章节，提取所有角色、地点、物品的属性设定。

已定义的角色列表：{char_list_str}

章节标题：{chapter.title}
章节内容：
{chapter.content[:3000]}

请提取以下类型的设定信息：
1. 角色属性：年龄、性别、外貌、性格、能力、身份、状态变化
2. 地点信息：地点名称、位置描述、特征
3. 物品设定：物品名称、功能、归属
4. 世界规则：法则、制度、限制

请用JSON格式返回，每个设定包含：
- type: "character"/"location"/"item"/"rule"
- name: 实体名称（角色请使用已定义的名称）
- property: 属性名（age/gender/appearance/ability/location等）
- value: 属性值
- quote: 原文引用（简短）
- confidence: 置信度(0-1)

返回格式：
```json
[
  {{"type": "character", "name": "张三", "property": "age", "value": "25", "quote": "张三今年二十五岁", "confidence": 0.9}},
  ...
]
```

只返回JSON数组，不要其他说明。如果没有提取到任何设定，返回空数组 []。"""

        try:
            result = await self.ai_service.generate_text(
                prompt=prompt,
                temperature=0.3
            )

            # generate_text 返回 Dict，需要提取 content 字段
            if isinstance(result, dict):
                content = result.get("content", "")
            else:
                content = str(result)

            entities_data = self._parse_ai_response(content)
            snapshots = []

            for entity_data in entities_data:
                entity_name = entity_data.get("name", "")
                entity_type = entity_data.get("type", "character")
                
                # 尝试关联已有角色
                matched_char = None
                if entity_type == "character":
                    matched_char = self._find_matching_character(entity_name, characters)
                
                entity_id = matched_char.id if matched_char else f"{entity_type}_{entity_name}"
                
                snapshot = EntitySnapshot(
                    project_id=chapter.project_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=matched_char.name if matched_char else entity_name,
                    property_name=entity_data.get("property", "description"),
                    property_value=self._format_value(entity_data.get("value", "")),
                    property_type=self._detect_type(entity_data.get("value", "")),
                    source_chapter_id=chapter.id,
                    source_quote=entity_data.get("quote", "")[:200],
                    source_context="",
                    confidence=float(entity_data.get("confidence", 0.8)),
                    ai_model=ai_model or "default"
                )
                snapshots.append(snapshot)

            logger.info(f"AI提取实体: chapter_id={chapter.id}, count={len(snapshots)}")
            return snapshots

        except Exception as e:
            logger.error(f"AI提取实体失败: {str(e)}")
            return []

    async def _extract_with_rules(
        self, 
        chapter: Chapter, 
        characters: List[Character],
        db: AsyncSession
    ) -> List[EntitySnapshot]:
        """使用规则匹配提取实体（降级方案）"""
        snapshots = []
        seen_entities = set()  # 用于去重

        # 提取角色属性
        snapshots.extend(self._extract_character_attrs(chapter, characters, seen_entities))

        # 提取地点
        snapshots.extend(self._extract_locations(chapter, seen_entities))

        # 提取规则设定
        snapshots.extend(self._extract_rules(chapter, seen_entities))

        logger.info(f"规则提取实体: chapter_id={chapter.id}, count={len(snapshots)}")
        return snapshots

    def _extract_character_attrs(
        self, 
        chapter: Chapter, 
        characters: List[Character],
        seen: set
    ) -> List[EntitySnapshot]:
        """提取角色属性"""
        snapshots = []
        content = chapter.content

        # 年龄模式（增强版）
        age_patterns = [
            # 阿拉伯数字: 小明20岁、今年20岁的小明
            (r'([\u4e00-\u9fa5]{2,4})(\d{1,3})岁', lambda m: (m.group(1), m.group(2))),
            (r'(\d{1,3})岁的([\u4e00-\u9fa5]{2,4})', lambda m: (m.group(2), m.group(1))),
            # 中文数字: 二十岁、二十多岁
            (r'([\u4e00-\u9fa5]{2,4})[今年是有]?([零一二两三四五六七八九十百]+)多?岁', 
             lambda m: (m.group(1), chinese_to_number(m.group(2)))),
            (r'([零一二两三四五六七八九十百]+)多?岁的([\u4e00-\u9fa5]{2,4})',
             lambda m: (m.group(2), chinese_to_number(m.group(1)))),
        ]

        for pattern, extractor in age_patterns:
            for match in re.finditer(pattern, content):
                try:
                    name, age = extractor(match)
                    if age is None:
                        continue
                    age = str(age)
                    
                    # 去重
                    key = f"char_{name}:age"
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    # 尝试匹配已有角色
                    matched_char = self._find_matching_character(name, characters)
                    entity_id = matched_char.id if matched_char else f"char_{name}"
                    entity_name = matched_char.name if matched_char else name
                    
                    # 判断置信度
                    _, confidence = normalize_age_value(match.group(0))
                    
                    snapshot = EntitySnapshot(
                        project_id=chapter.project_id,
                        entity_type="character",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        property_name="age",
                        property_value=age,
                        property_type="number",
                        source_chapter_id=chapter.id,
                        source_quote=match.group(0),
                        source_context=content[max(0, match.start()-30):min(len(content), match.end()+30)],
                        confidence=confidence,
                        ai_model="rule_based"
                    )
                    snapshots.append(snapshot)
                except Exception as e:
                    logger.debug(f"解析年龄失败: {e}")
                    continue

        # 性别模式（增强版）
        gender_patterns = [
            (r'([\u4e00-\u9fa5]{2,4})是[个一位名]?(男|女)[性人子的]', lambda m: (m.group(1), m.group(2))),
            (r'(男|女)[主人]角([\u4e00-\u9fa5]{2,4})', lambda m: (m.group(2), m.group(1))),
            (r'([\u4e00-\u9fa5]{2,4})[,，]?[这那]个?(男|女)孩', lambda m: (m.group(1), m.group(2))),
            (r'(他|她)叫([\u4e00-\u9fa5]{2,4})', lambda m: (m.group(2), "男" if m.group(1) == "他" else "女")),
        ]

        for pattern, extractor in gender_patterns:
            for match in re.finditer(pattern, content):
                try:
                    name, gender = extractor(match)
                    
                    key = f"char_{name}:gender"
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    matched_char = self._find_matching_character(name, characters)
                    entity_id = matched_char.id if matched_char else f"char_{name}"
                    entity_name = matched_char.name if matched_char else name
                    
                    snapshot = EntitySnapshot(
                        project_id=chapter.project_id,
                        entity_type="character",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        property_name="gender",
                        property_value=gender,
                        property_type="string",
                        source_chapter_id=chapter.id,
                        source_quote=match.group(0),
                        source_context=content[max(0, match.start()-20):min(len(content), match.end()+20)],
                        confidence=0.7,
                        ai_model="rule_based"
                    )
                    snapshots.append(snapshot)
                except Exception:
                    continue

        return snapshots

    def _extract_locations(self, chapter: Chapter, seen: set) -> List[EntitySnapshot]:
        """提取地点信息"""
        snapshots = []
        content = chapter.content

        # 地点后缀（扩展）
        location_suffixes = [
            "村", "镇", "城", "市", "省", "国", "州", "府", "县",
            "森林", "山", "山脉", "河", "河流", "湖", "海", "岛", "洲",
            "堡", "殿", "宫", "府", "阁", "楼", "塔", "庙", "寺", "观",
            "学院", "学校", "宗门", "门派", "帮", "会", "盟",
            "谷", "洞", "穴", "崖", "峰", "岭"
        ]

        for suffix in location_suffixes:
            pattern = rf'([\u4e00-\u9fa5]{{2,6}}{suffix})'
            for match in re.finditer(pattern, content):
                location_name = match.group(1)
                
                # 过滤常见非地点词
                if any(w in location_name for w in ['什么', '这个', '那个', '一个']):
                    continue
                
                key = f"loc_{location_name}:name"
                if key in seen:
                    continue
                seen.add(key)

                snapshot = EntitySnapshot(
                    project_id=chapter.project_id,
                    entity_type="location",
                    entity_id=f"loc_{location_name}",
                    entity_name=location_name,
                    property_name="name",
                    property_value=location_name,
                    property_type="string",
                    source_chapter_id=chapter.id,
                    source_quote=location_name,
                    source_context=content[max(0, match.start()-30):min(len(content), match.end()+30)],
                    confidence=0.6,
                    ai_model="rule_based"
                )
                snapshots.append(snapshot)

        return snapshots

    def _extract_rules(self, chapter: Chapter, seen: set) -> List[EntitySnapshot]:
        """提取世界观规则"""
        snapshots = []
        content = chapter.content

        # 规则模式（增强）
        rule_patterns = [
            r'([\u4e00-\u9fa5]{2,20}(?:规则|法则|定律|禁忌|铁律))',
            r'((?:修炼|晋级|突破)[\u4e00-\u9fa5]{2,30})',
            r'([\u4e00-\u9fa5]{2,10}境界[\u4e00-\u9fa5]{0,20})',
        ]

        for pattern in rule_patterns:
            for match in re.finditer(pattern, content):
                rule_text = match.group(1).strip()
                
                if len(rule_text) < 4:
                    continue
                
                key = f"rule:{rule_text[:20]}"
                if key in seen:
                    continue
                seen.add(key)

                snapshot = EntitySnapshot(
                    project_id=chapter.project_id,
                    entity_type="rule",
                    entity_id=f"rule_{hash(rule_text) % 100000}",
                    entity_name=rule_text[:50],
                    property_name="description",
                    property_value=rule_text,
                    property_type="string",
                    source_chapter_id=chapter.id,
                    source_quote=rule_text[:100],
                    source_context=content[max(0, match.start()-50):min(len(content), match.end()+50)],
                    confidence=0.5,
                    ai_model="rule_based"
                )
                snapshots.append(snapshot)

        return snapshots

    def _parse_ai_response(self, response: str) -> List[Dict[str, Any]]:
        """解析AI返回的JSON"""
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "entities" in data:
                return data["entities"]
        except json.JSONDecodeError:
            pass

        # 提取JSON代码块
        code_block = re.search(r'```(?:json)?\s*([\[\{].*?[\]\}])\s*```', response, re.DOTALL)
        if code_block:
            try:
                data = json.loads(code_block.group(1))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
        
        # 尝试直接找数组
        array_match = re.search(r'\[[\s\S]*\]', response)
        if array_match:
            try:
                data = json.loads(array_match.group(0))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

        logger.warning("无法解析AI响应格式")
        return []

    def _format_value(self, value: Any) -> str:
        """格式化属性值"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value).strip()

    def _detect_type(self, value: Any) -> str:
        """检测值类型"""
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, (dict, list)):
            return "json"
        # 尝试判断是否为数字字符串
        try:
            float(str(value))
            return "number"
        except ValueError:
            pass
        return "string"

    async def batch_extract(
        self,
        chapters: List[Chapter],
        db: AsyncSession,
        ai_provider: str = None,
        ai_model: str = None
    ) -> Tuple[int, List[str]]:
        """批量提取章节实体"""
        total_extracted = 0
        error_chapters = []

        if not chapters:
            return 0, []

        project_id = chapters[0].project_id

        # 预加载角色数据
        await self._get_project_characters(project_id, db)

        # 预加载已存在的快照键（避免每次查询数据库）
        existing_result = await db.execute(
            select(
                EntitySnapshot.entity_id,
                EntitySnapshot.property_name,
                EntitySnapshot.source_chapter_id
            ).where(EntitySnapshot.project_id == project_id)
        )
        existing_keys = set()
        for row in existing_result.all():
            existing_keys.add(f"{row[0]}:{row[1]}:{row[2]}")

        # 收集所有新快照
        all_new_snapshots = []
        
        logger.info(f"开始批量提取: 共 {len(chapters)} 章, 已存在 {len(existing_keys)} 条记录")

        for chapter in chapters:
            try:
                snapshots = await self.extract_from_chapter(chapter, db, ai_provider, ai_model)
                
                new_count = 0
                dup_count = 0
                for snapshot in snapshots:
                    # 内存中检查重复
                    key = f"{snapshot.entity_id}:{snapshot.property_name}:{snapshot.source_chapter_id}"
                    if key not in existing_keys:
                        all_new_snapshots.append(snapshot)
                        existing_keys.add(key)  # 防止本次批量内重复
                        new_count += 1
                    else:
                        dup_count += 1

                logger.info(f"章节提取完成: chapter={chapter.chapter_number}, 提取={len(snapshots)}, 新增={new_count}, 重复={dup_count}")

            except Exception as e:
                logger.error(f"章节提取失败: chapter_id={chapter.id}, error={str(e)}", exc_info=True)
                error_chapters.append(chapter.id)

        logger.info(f"提取汇总: 待保存 {len(all_new_snapshots)} 条新记录")

        # 批量保存
        if all_new_snapshots:
            try:
                for snapshot in all_new_snapshots:
                    db.add(snapshot)
                await db.commit()
                total_extracted = len(all_new_snapshots)
                logger.info(f"批量保存完成: project_id={project_id}, total={total_extracted}")
            except Exception as e:
                logger.error(f"批量保存失败: {str(e)}", exc_info=True)
                await db.rollback()
                error_chapters.append("batch_save")
                return 0, error_chapters
        else:
            logger.info("无新记录需要保存")

        return total_extracted, error_chapters

    def clear_cache(self):
        """清除角色缓存"""
        self._character_cache.clear()
