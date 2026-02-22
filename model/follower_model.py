import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from model.model import get_async_session, FollowerTable, SendHistory
from strategy.context import TwitterContent


# ---------------------------------------------------------------------------
# 基础 CRUD
# ---------------------------------------------------------------------------

async def get_all_follower() -> List[FollowerTable]:
    """获取所有需要关注的用户"""
    async with get_async_session() as session:
        result = await session.execute(select(FollowerTable))
        return result.scalars().all()


async def add_new_follower(user_id: str, category: str = "default", source: str = "twitter"):
    """添加新的关注用户"""
    async with get_async_session() as session:
        session.add(FollowerTable(user_id=user_id, category=category, source=source))


async def get_all_category() -> List[str]:
    """获取所有分类"""
    async with get_async_session() as session:
        result = await session.execute(select(FollowerTable.category).distinct())
        return result.scalars().all()


async def update_follower(user_id: str, category: str):
    """更新用户分类"""
    async with get_async_session() as session:
        follower = await session.get(FollowerTable, user_id)
        if follower:
            follower.category = category
            session.add(follower)


async def delete_follower(user_id: str):
    """删除用户"""
    async with get_async_session() as session:
        follower = await session.get(FollowerTable, user_id)
        if follower:
            await session.delete(follower)

async def select_follower_by_category(category: str) -> List[FollowerTable]:
    """根据分类获取用户"""
    async with get_async_session() as session:
        result = await session.execute(select(FollowerTable).where(FollowerTable.category == category))
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Scheduler 专用查询/写入
# ---------------------------------------------------------------------------

async def get_active_user_ids() -> List[str]:
    """获取所有活跃用户 ID 列表（category != 'disable'）"""
    async with get_async_session() as session:
        result = await session.execute(
            select(FollowerTable.user_id).where(FollowerTable.category != "disable")  # type: ignore[arg-type]
        )
        return result.scalars().all()


async def get_follower_snapshot(user_id: str) -> Optional[FollowerTable]:
    """
    获取单个用户信息快照（expire_on_commit=False 保证 session 关闭后仍可读取字段）。
    """
    async with get_async_session() as session:
        return await session.get(FollowerTable, user_id)


async def save_post_result(
        user_id: str,
        content: TwitterContent,
        dt: datetime,
        target_chat_id: str,
):
    """
    将成功发送的帖子写入 SendHistory，并更新 FollowerTable 状态。
    """
    async with get_async_session() as session:
        media_snapshot_str = json.dumps(content.media_list) if content.media_list else None
        history = SendHistory(
            author=content.author,
            content=content.content[:200] if content.content else "",  # type: ignore[index]
            link=content.link,
            media_snapshot=media_snapshot_str,
            chat_id=str(target_chat_id),
            create_time=dt,
            send_time=datetime.now(),
        )
        session.add(history)

        follower = await session.get(FollowerTable, user_id)
        if follower:
            follower.latest_post_datetime = dt
            follower.latest_post_link = content.link
            follower.latest_send_datetime = datetime.now()
            session.add(follower)
