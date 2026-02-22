import os
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

from sqlalchemy import Column, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import Field, SQLModel
from datetime import datetime

sqlite_file_name = "database.db"
# 获取项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sqlite_async_url = f"sqlite+aiosqlite:///{project_root}/{sqlite_file_name}"

# 异步引擎：用于所有业务查询/写入
async_engine = create_async_engine(sqlite_async_url, echo=True)
AsyncSessionFactory = async_sessionmaker(async_engine, expire_on_commit=False)


class FollowerTable(SQLModel, table=True):
    """
    用于保存所有需要关注的用户
    """

    __tablename__ = "follower_table"
    # 用户id
    user_id: str = Field(primary_key=True)
    # 所属分组
    category: str = Field(default="default")
    # 来源
    source: str = Field(default="twitter")
    # 上次最后发帖的link
    latest_post_link: Optional[str] = Field(default=None)
    # 标准化的datetime字段（用于数据库存储和比较）
    latest_post_datetime: Optional[datetime] = Field(default=None, sa_column=Column(DateTime,nullable=True))
    # 上次发送的时间
    latest_send_datetime: Optional[datetime] = Field(default=None, sa_column=Column(DateTime,nullable=True))

    class Config:
        arbitrary_types_allowed = True


class SendHistory(SQLModel, table=True):
    """
    用于保存已经发送过的内容
    """
    __tablename__ = "send_history"

    id: int = Field(primary_key=True)
    author: str
    content: str
    link: str
    media_snapshot: Optional[str] = Field(default=None) # 快照字段
    chat_id: str
    create_time: datetime
    send_time: datetime = Field(default_factory=datetime.now)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    异步 Session 上下文管理器。
    用法：async with get_async_session() as session: ...
    异常时自动回滚，结束后自动关闭。
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise



