"""章节关系分析服务 - 分析章节之间的逻辑关系并构建图谱"""
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models_new import ChapterLink, ThinkingChain
from app.models.chapter import Chapter
from app.services.ai_service import AIService
from app.logger import get_logger

logger = get_logger(__name__)

# 关系类型定义
LINK_TYPES = {
    "causality": {"name": "因果关系", "description": "前一章节的事件导致后续章节的结果"},
    "foreshadowing": {"name": "伏笔埋设", "description": "前一章节埋下伏笔"},
    "callback": {"name": "伏笔回收", "description": "后续章节回收之前的伏笔"},
    "parallel": {"name": "平行叙事", "description": "两个章节描述同时发生的事件"},
    "contrast": {"name": "对比冲突", "description": "两个章节形成对比或冲突"},
    "continuation": {"name": "承上启下", "description": "自然的故事延续"}
}


@dataclass
class LinkAnalysis:
    """关系分析结果"""
    from_chapter_id: str
    to_chapter_id: str
    link_type: str
    description: str
    reasoning_steps: List[Dict[str, str]]
    confidence: float
    importance_score: float


class LinkAnalyzer:
    """章节关系分析器 - 分析章节之间的逻辑关系"""

    # 伏笔关键词
    FORESHADOWING_KEYWORDS = [
        "伏笔", "暗示", "预示", "似乎", "或许", "可能", "隐约",
        "不知为何", "莫名", "直觉", "预感", "隐隐", "总觉得"
    ]
    
    # 回收关键词
    CALLBACK_KEYWORDS = [
        "想起", "回忆", "终于", "原来", "难怪", "恍然大悟",
        "这才明白", "突然想到", "想起之前", "早知道", "当初"
    ]
    
    # 冲突关键词
    CONFLICT_KEYWORDS = [
        "冲突", "对立", "矛盾", "对抗", "敌对", "反对",
        "但是", "然而", "却", "相反", "截然不同"
    ]

    def __init__(self, ai_service: AIService = None):
        self.ai_service = ai_service

    async def analyze_all_relationships(
        self,
        project_id: str,
        db: AsyncSession,
        ai_provider: str = None,
        ai_model: str = None
    ) -> List[ChapterLink]:
        """分析项目中所有章节的关系"""
        result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id
            ).order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()

        if len(chapters) < 2:
            logger.warning(f"章节数量不足: project_id={project_id}, count={len(chapters)}")
            return []

        logger.info(f"开始分析章节关系: project_id={project_id}, total={len(chapters)}")

        links = []
        
        # 1. 分析相邻章节关系
        adjacent_links = await self._analyze_adjacent_chapters(
            chapters, ai_provider, ai_model
        )
        links.extend(adjacent_links)
        
        # 2. 分析伏笔-回收关系（非相邻章节）
        foreshadowing_links = await self._analyze_foreshadowing(
            chapters, ai_provider, ai_model
        )
        links.extend(foreshadowing_links)
        
        # 3. 分析对比/冲突关系
        contrast_links = await self._analyze_contrasts(
            chapters, ai_provider, ai_model
        )
        links.extend(contrast_links)

        logger.info(f"章节关系分析完成: total_links={len(links)}")
        return links

    async def _analyze_adjacent_chapters(
        self,
        chapters: List[Chapter],
        ai_provider: str = None,
        ai_model: str = None
    ) -> List[ChapterLink]:
        """分析相邻章节的关系"""
        links = []

        for i in range(len(chapters) - 1):
            chapter_a = chapters[i]
            chapter_b = chapters[i + 1]

            if self.ai_service:
                link = await self._analyze_with_ai(
                    chapter_a, chapter_b, 
                    ai_provider, ai_model,
                    context="adjacent"
                )
            else:
                link = self._analyze_with_rules(chapter_a, chapter_b)

            if link:
                links.append(link)

        return links

    async def _analyze_foreshadowing(
        self,
        chapters: List[Chapter],
        ai_provider: str = None,
        ai_model: str = None
    ) -> List[ChapterLink]:
        """分析伏笔-回收关系"""
        links = []
        
        # 先找出所有可能包含伏笔的章节
        foreshadowing_chapters = []
        for ch in chapters:
            if ch.content and any(kw in ch.content for kw in self.FORESHADOWING_KEYWORDS):
                foreshadowing_chapters.append(ch)
        
        # 找出所有可能回收伏笔的章节
        callback_chapters = []
        for ch in chapters:
            if ch.content and any(kw in ch.content for kw in self.CALLBACK_KEYWORDS):
                callback_chapters.append(ch)
        
        # 匹配伏笔和回收
        for fch in foreshadowing_chapters:
            for cch in callback_chapters:
                # 回收必须在伏笔之后
                if cch.chapter_number <= fch.chapter_number:
                    continue
                
                # 间隔不能太大（通常5-20章以内）
                gap = cch.chapter_number - fch.chapter_number
                if gap < 2 or gap > 30:
                    continue
                
                if self.ai_service:
                    link = await self._analyze_with_ai(
                        fch, cch,
                        ai_provider, ai_model,
                        context="foreshadowing"
                    )
                    if link and link.link_type in ["foreshadowing", "callback", "causality"]:
                        links.append(link)
                else:
                    # 简单规则：如果两章都有相关关键词，认为有关系
                    link = self._create_foreshadowing_link(fch, cch)
                    if link:
                        links.append(link)
        
        return links

    async def _analyze_contrasts(
        self,
        chapters: List[Chapter],
        ai_provider: str = None,
        ai_model: str = None
    ) -> List[ChapterLink]:
        """分析对比/冲突关系"""
        links = []

        if not self.ai_service:
            return links  # 对比分析需要AI

        # 构建章节ID到索引的映射
        chapter_index_map = {ch.id: idx for idx, ch in enumerate(chapters)}

        # 找出可能有冲突的章节
        conflict_chapters = []
        for ch in chapters:
            if ch.content and any(kw in ch.content for kw in self.CONFLICT_KEYWORDS):
                conflict_chapters.append(ch)

        # 分析冲突章节与前面章节的关系
        for cch in conflict_chapters:
            # 获取当前章节在列表中的索引
            current_idx = chapter_index_map.get(cch.id)
            if current_idx is None or current_idx < 1:
                continue

            # 查看前5章是否有对比关系
            start_idx = max(0, current_idx - 5)
            for i in range(start_idx, current_idx):
                prev_ch = chapters[i]
                link = await self._analyze_with_ai(
                    prev_ch, cch,
                    ai_provider, ai_model,
                    context="contrast"
                )
                if link and link.link_type in ["contrast", "causality"]:
                    links.append(link)

        return links

    async def _analyze_with_ai(
        self,
        chapter_a: Chapter,
        chapter_b: Chapter,
        ai_provider: str = None,
        ai_model: str = None,
        context: str = "general"
    ) -> Optional[ChapterLink]:
        """使用AI分析两个章节的关系"""
        try:
            # 构建提示词
            prompt = self._build_analysis_prompt(chapter_a, chapter_b, context)

            result = await self.ai_service.generate_text(
                prompt=prompt,
                temperature=0.3
            )

            # generate_text 返回 Dict，需要提取 content 字段
            if isinstance(result, dict):
                response_text = result.get("content", "")
            else:
                response_text = str(result)

            link_data = self._parse_ai_response(response_text)

            if not link_data:
                return None
            
            # 如果AI判断没有关系
            if link_data.get("link_type") == "none":
                return None

            link = ChapterLink(
                project_id=chapter_a.project_id,
                from_chapter_id=chapter_a.id,
                from_chapter_title=chapter_a.title,
                to_chapter_id=chapter_b.id,
                to_chapter_title=chapter_b.title,
                link_type=link_data.get("link_type", "continuation"),
                link_type_display=LINK_TYPES.get(link_data.get("link_type", ""), {}).get("name", "承上启下"),
                description=link_data.get("description", ""),
                from_element=link_data.get("from_element", ""),
                to_element=link_data.get("to_element", ""),
                reasoning_chain=json.dumps(link_data.get("reasoning_chain", {}), ensure_ascii=False),
                strength=float(link_data.get("strength", 0.5)),
                importance_score=float(link_data.get("importance_score", 50)),
                confidence=float(link_data.get("confidence", 0.7)),
                ai_model=ai_model or "default",
                time_gap=chapter_b.chapter_number - chapter_a.chapter_number
            )

            return link

        except Exception as e:
            logger.error(f"AI分析章节关系失败: {str(e)}")
            return None

    def _analyze_with_rules(self, chapter_a: Chapter, chapter_b: Chapter) -> Optional[ChapterLink]:
        """规则分析相邻章节关系"""
        link_type = "continuation"
        description = f"第{chapter_a.chapter_number}章到第{chapter_b.chapter_number}章的延续"
        strength = 0.5
        importance_score = 50

        content_a = chapter_a.content or ""
        content_b = chapter_b.content or ""

        # 检测伏笔
        if any(kw in content_a for kw in self.FORESHADOWING_KEYWORDS):
            if any(kw in content_b for kw in self.CALLBACK_KEYWORDS):
                link_type = "foreshadowing"
                description = f"第{chapter_a.chapter_number}章埋下伏笔，第{chapter_b.chapter_number}章开始回收"
                strength = 0.7
                importance_score = 70

        # 检测冲突
        if any(kw in content_b for kw in self.CONFLICT_KEYWORDS):
            link_type = "contrast"
            description = f"第{chapter_b.chapter_number}章与前文形成对比或冲突"
            strength = 0.6
            importance_score = 65

        link = ChapterLink(
            project_id=chapter_a.project_id,
            from_chapter_id=chapter_a.id,
            from_chapter_title=chapter_a.title,
            to_chapter_id=chapter_b.id,
            to_chapter_title=chapter_b.title,
            link_type=link_type,
            link_type_display=LINK_TYPES.get(link_type, {}).get("name", "承上启下"),
            description=description,
            reasoning_chain=json.dumps({
                "method": "rule_based",
                "from_title": chapter_a.title,
                "to_title": chapter_b.title
            }, ensure_ascii=False),
            strength=strength,
            importance_score=importance_score,
            confidence=0.5,
            ai_model="rule_based",
            time_gap=1
        )

        return link

    def _create_foreshadowing_link(
        self, 
        foreshadowing_ch: Chapter, 
        callback_ch: Chapter
    ) -> Optional[ChapterLink]:
        """创建伏笔-回收关系"""
        gap = callback_ch.chapter_number - foreshadowing_ch.chapter_number
        
        # 根据间隔调整重要性
        importance = min(90, 50 + gap * 2)
        strength = min(0.9, 0.5 + gap * 0.02)
        
        return ChapterLink(
            project_id=foreshadowing_ch.project_id,
            from_chapter_id=foreshadowing_ch.id,
            from_chapter_title=foreshadowing_ch.title,
            to_chapter_id=callback_ch.id,
            to_chapter_title=callback_ch.title,
            link_type="foreshadowing",
            link_type_display="伏笔回收",
            description=f"第{foreshadowing_ch.chapter_number}章埋下的伏笔在第{callback_ch.chapter_number}章回收（间隔{gap}章）",
            reasoning_chain=json.dumps({
                "method": "keyword_matching",
                "gap": gap
            }, ensure_ascii=False),
            strength=strength,
            importance_score=importance,
            confidence=0.4,
            ai_model="rule_based",
            time_gap=gap
        )

    def _build_analysis_prompt(
        self, 
        chapter_a: Chapter, 
        chapter_b: Chapter,
        context: str
    ) -> str:
        """构建分析提示词"""
        context_hints = {
            "adjacent": "这是两个相邻的章节，请分析它们之间的延续和发展关系。",
            "foreshadowing": "请特别关注是否存在伏笔埋设和回收的关系。",
            "contrast": "请特别关注是否存在对比、冲突或反转的关系。",
            "general": "请综合分析这两个章节之间可能存在的关系。"
        }
        
        content_a = (chapter_a.content or "")[:1500]
        content_b = (chapter_b.content or "")[:1500]
        
        return f"""分析以下两个小说章节之间的关系。

{context_hints.get(context, context_hints["general"])}

【第{chapter_a.chapter_number}章：{chapter_a.title}】
{content_a}

【第{chapter_b.chapter_number}章：{chapter_b.title}】
{content_b}

请分析这两个章节之间的关系，并返回JSON格式结果：

关系类型说明：
- causality: 因果关系（前一章事件导致后续结果）
- foreshadowing: 伏笔埋设（前一章埋下伏笔，后续回收）
- callback: 伏笔回收（后续章节回收之前的伏笔）
- parallel: 平行叙事（同时发生的不同事件）
- contrast: 对比冲突（形成对比或冲突）
- continuation: 承上启下（自然延续）
- none: 无明显关系

请用JSON格式返回：
```json
{{
  "link_type": "关系类型",
  "description": "关系描述（一句话）",
  "from_element": "前一章的关键元素",
  "to_element": "后一章的对应元素",
  "reasoning_chain": {{
    "observation": "观察到的现象",
    "analysis": "分析推理",
    "conclusion": "得出的结论"
  }},
  "strength": 0.7,
  "importance_score": 70,
  "confidence": 0.8
}}
```

只返回JSON，不要其他说明。如果没有明显关系，link_type设为"none"。"""

    def _parse_ai_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析AI响应"""
        try:
            data = json.loads(response)
            return data
        except json.JSONDecodeError:
            pass

        # 提取JSON代码块
        import re
        match = re.search(r'```(?:json)?\s*([\{\[].*?[\}\]])\s*```', response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return data
            except:
                pass
        
        # 尝试直接找JSON对象
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            try:
                data = json.loads(match.group(0))
                return data
            except:
                pass

        logger.warning(f"无法解析AI响应")
        return None

    async def save_links(self, links: List[ChapterLink], db: AsyncSession) -> Tuple[int, List[str]]:
        """保存章节关系"""
        if not links:
            return 0, []

        error_ids = []
        project_id = links[0].project_id

        # 预加载已存在的关系键
        existing_result = await db.execute(
            select(
                ChapterLink.from_chapter_id,
                ChapterLink.to_chapter_id,
                ChapterLink.link_type
            ).where(ChapterLink.project_id == project_id)
        )
        existing_keys = set()
        for row in existing_result.all():
            existing_keys.add(f"{row[0]}:{row[1]}:{row[2]}")

        # 筛选新关系
        new_links = []
        for link in links:
            key = f"{link.from_chapter_id}:{link.to_chapter_id}:{link.link_type}"
            if key not in existing_keys:
                new_links.append(link)
                existing_keys.add(key)

        # 批量保存
        if new_links:
            try:
                db.add_all(new_links)
                await db.commit()
                logger.info(f"保存关系完成: saved={len(new_links)}")
            except Exception as e:
                logger.error(f"批量保存关系失败: {str(e)}")
                await db.rollback()
                error_ids.append("batch_save")
                return 0, error_ids

        return len(new_links), error_ids

    async def get_chapter_relationships(
        self,
        project_id: str,
        db: AsyncSession,
        chapter_id: str = None,
        link_type: str = None
    ) -> List[ChapterLink]:
        """获取章节关系"""
        query = select(ChapterLink).where(ChapterLink.project_id == project_id)

        if chapter_id:
            query = query.where(
                or_(
                    ChapterLink.from_chapter_id == chapter_id,
                    ChapterLink.to_chapter_id == chapter_id
                )
            )

        if link_type:
            query = query.where(ChapterLink.link_type == link_type)

        query = query.order_by(ChapterLink.importance_score.desc())

        result = await db.execute(query)
        return result.scalars().all()

    async def build_graph_data(
        self,
        project_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """构建图谱数据"""
        links = await self.get_chapter_relationships(project_id, db)

        # 收集节点
        chapter_ids = set()
        for link in links:
            chapter_ids.add(link.from_chapter_id)
            chapter_ids.add(link.to_chapter_id)

        # 查询章节信息
        if chapter_ids:
            chapters = await db.execute(
                select(Chapter.id, Chapter.title, Chapter.chapter_number).where(
                    Chapter.id.in_(list(chapter_ids))
                )
            )
            chapter_map = {ch[0]: ch for ch in chapters.all()}
        else:
            chapter_map = {}

        # 构建节点（计算重要性）
        node_link_count = {}
        for link in links:
            node_link_count[link.from_chapter_id] = node_link_count.get(link.from_chapter_id, 0) + 1
            node_link_count[link.to_chapter_id] = node_link_count.get(link.to_chapter_id, 0) + 1

        nodes = []
        for ch_id in chapter_ids:
            ch = chapter_map.get(ch_id)
            if ch:
                count = node_link_count.get(ch_id, 0)
                importance = min(100, 30 + count * 15)
                
                nodes.append({
                    "id": ch_id,
                    "title": ch[1],
                    "chapterNumber": ch[2],
                    "importance": importance,
                    "size": min(35, 12 + count * 4)
                })

        # 排序节点
        nodes.sort(key=lambda x: x["chapterNumber"])

        # 构建边
        edges = []
        for link in links:
            edges.append({
                "source": link.from_chapter_id,
                "target": link.to_chapter_id,
                "type": link.link_type,
                "description": link.description or "",
                "strength": link.strength or 0.5,
                "importance": link.importance_score or 50
            })

        return {
            "nodes": nodes,
            "links": edges,
            "summary": {
                "totalNodes": len(nodes),
                "totalLinks": len(edges),
                "linkTypes": list(set(link.link_type for link in links)) if links else []
            }
        }

    async def analyze_chapter_importance(
        self,
        project_id: str,
        chapter_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """分析章节重要性"""
        links = await self.get_chapter_relationships(project_id, db, chapter_id=chapter_id)

        incoming = [l for l in links if l.to_chapter_id == chapter_id]
        outgoing = [l for l in links if l.from_chapter_id == chapter_id]

        # 计算综合重要性
        base_score = 50
        incoming_score = len(incoming) * 12
        outgoing_score = len(outgoing) * 10
        
        # 特殊关系加分
        special_types = ["foreshadowing", "callback", "causality"]
        special_count = sum(1 for l in links if l.link_type in special_types)
        special_score = special_count * 8
        
        importance = min(100, base_score + incoming_score + outgoing_score + special_score)

        return {
            "chapterId": chapter_id,
            "importanceScore": importance,
            "incomingCount": len(incoming),
            "outgoingCount": len(outgoing),
            "specialRelations": special_count,
            "incoming": [
                {
                    "fromChapterId": l.from_chapter_id,
                    "title": l.from_chapter_title,
                    "type": l.link_type,
                    "typeDisplay": LINK_TYPES.get(l.link_type, {}).get("name", l.link_type),
                    "description": l.description
                }
                for l in incoming
            ],
            "outgoing": [
                {
                    "toChapterId": l.to_chapter_id,
                    "title": l.to_chapter_title,
                    "type": l.link_type,
                    "typeDisplay": LINK_TYPES.get(l.link_type, {}).get("name", l.link_type),
                    "description": l.description
                }
                for l in outgoing
            ]
        }
