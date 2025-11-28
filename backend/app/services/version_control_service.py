"""版本控制服务 - 轻量级章节版本管理"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json
from datetime import datetime

from app.models.chapter_version import ChapterVersion
from app.models.chapter import Chapter
from app.logger import get_logger

logger = get_logger(__name__)


class VersionControlService:
    """轻量级版本控制服务 - 核心功能：自动备份、一键恢复"""

    async def create_version(
        self,
        db: AsyncSession,
        chapter_id: str,
        user_id: str,
        source: str = "user",
        ai_provider: Optional[str] = None,
        ai_model: Optional[str] = None,
        generation_prompt: Optional[str] = None
    ) -> str:
        """
        创建新版本

        Args:
            db: 数据库会话
            chapter_id: 章节ID
            user_id: 用户ID
            source: 版本来源 (user:手动编辑, ai:AI生成, restore:版本恢复)
            ai_provider: AI提供商（可选）
            ai_model: AI模型（可选）
            generation_prompt: 生成提示词（可选）

        Returns:
            版本ID
        """
        # 获取章节当前内容
        result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
        chapter = result.scalar_one_or_none()

        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        # 获取下一个版本号
        version_number = await self._get_next_version_number(db, chapter_id)

        # 创建版本记录（备份所有章节字段，保持数据完整性）
        version = ChapterVersion(
            chapter_id=chapter_id,
            # 内容相关字段
            title=chapter.title or "",
            content=chapter.content or "",
            summary=chapter.summary or "",
            word_count=chapter.word_count or 0,
            status=chapter.status or "draft",
            # 大纲关联字段
            outline_id=chapter.outline_id,
            sub_index=chapter.sub_index or 1,
            # 大纲展开规划
            expansion_plan=chapter.expansion_plan,
            # 版本元数据
            version_number=version_number,
            source=source,
            created_by=user_id,
            # AI生成参数
            ai_provider=ai_provider,
            ai_model=ai_model,
            generation_prompt=generation_prompt
        )

        db.add(version)
        await db.commit()
        await db.refresh(version)

        logger.info(f"版本创建成功: chapter_id={chapter_id}, version={version_number}, source={source}, title='{chapter.title}'")
        return version.id

    async def restore_version(
        self,
        db: AsyncSession,
        chapter_id: str,
        version_id: str,
        user_id: str
    ) -> bool:
        """
        恢复到指定版本

        Args:
            db: 数据库会话
            chapter_id: 章节ID
            version_id: 版本ID
            user_id: 操作用户ID

        Returns:
            是否成功
        """
        # 获取版本记录
        result = await db.execute(select(ChapterVersion).where(ChapterVersion.id == version_id))
        version = result.scalar_one_or_none()

        if not version:
            raise ValueError(f"版本不存在: {version_id}")

        if version.chapter_id != chapter_id:
            raise ValueError(f"版本不属于该章节")

        # 获取章节
        result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
        chapter = result.scalar_one_or_none()

        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        # 恢复内容
        chapter.content = version.content
        chapter.word_count = version.word_count

        # 保存当前状态为一个新版本（记录恢复操作）
        await self.create_version(db, chapter_id, user_id, source="restore")

        await db.commit()

        logger.info(f"版本恢复成功: chapter_id={chapter_id}, version_id={version_id}")
        return True

    async def list_versions(
        self,
        db: AsyncSession,
        chapter_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取版本列表

        Args:
            db: 数据库会话
            chapter_id: 章节ID
            limit: 返回数量限制

        Returns:
            版本列表
        """
        result = await db.execute(
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == chapter_id)
            .order_by(ChapterVersion.created_at.desc())
            .limit(limit)
        )

        versions = result.scalars().all()

        return [
            {
                "id": v.id,
                "version_number": v.version_number,
                "word_count": v.word_count,
                "source": v.source,
                "created_at": v.created_at.isoformat(),
                "ai_provider": v.ai_provider,
                "ai_model": v.ai_model,
                "preview": (v.content or "")[:200] + "..." if len(v.content or "") > 200 else v.content
            }
            for v in versions
        ]

    async def get_version(self, db: AsyncSession, version_id: str) -> Optional[ChapterVersion]:
        """
        获取单个版本详情

        Args:
            db: 数据库会话
            version_id: 版本ID

        Returns:
            版本对象
        """
        result = await db.execute(select(ChapterVersion).where(ChapterVersion.id == version_id))
        return result.scalar_one_or_none()

    async def _get_next_version_number(self, db: AsyncSession, chapter_id: str) -> int:
        """
        获取下一个版本号

        Args:
            db: 数据库会话
            chapter_id: 章节ID

        Returns:
            下一个版本号
        """
        result = await db.execute(
            select(func.count())
            .where(ChapterVersion.chapter_id == chapter_id)
        )
        count = result.scalar() or 0
        return count + 1


# 单例
_version_control_service = None


def get_version_control_service() -> VersionControlService:
    """获取版本控制服务单例"""
    global _version_control_service
    if _version_control_service is None:
        _version_control_service = VersionControlService()
    return _version_control_service
