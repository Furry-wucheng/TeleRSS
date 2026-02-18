import os

from sqlalchemy import create_engine, Column, DateTime, func
from sqlmodel import Field, SQLModel
from datetime import datetime
from typing import Optional

sqlite_file_name = "database.db"
# 获取项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sqlite_url = f"sqlite:///{project_root}/{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)


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


def create_db_and_table():
    SQLModel.metadata.create_all(engine)


def get_session():
    from sqlmodel import Session
    return Session(engine)


if __name__ == '__main__':
    one = get_session().exec(func.count(FollowerTable.user_id)).scalar()
    print(one)
