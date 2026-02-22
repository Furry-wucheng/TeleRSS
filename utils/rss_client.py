from typing import Any, Optional

from pydantic import BaseModel, model_validator
import xml.etree.ElementTree as ET
import asyncio
import httpx
from datetime import datetime

from utils.config_manager import get_config, ConfigError
from utils.date_handler import parse_date

class RssResponse(BaseModel):
    title: str = ""
    description: str = ""
    link: str = ""
    guid: str = ""
    isPermaLink: bool = False
    pubDate: str = ""
    pubDatetime: Optional[datetime] = None
    author: str = ""

    @model_validator(mode='after')
    def parse_datetime(self):
        if self.pubDate:
            self.pubDatetime = parse_date(self.pubDate)
        return self

class RssClient:
    def __init__(self, base_url: str = None):
        self.__base_url = base_url
        self.__client = None

    async def __aenter__(self):
        self.__client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.__client:
            await self.__client.aclose()
        self.__client = None

    @classmethod
    def create_from_config(cls, section: str = "rss", option: str = "rss_base_url",
                           **kwargs: Any) -> "RssClient":
        base_url = get_config(section, option, required=True)
        if not base_url:
            raise ConfigError(f"[{section}] {option} 未配置")
        return cls(base_url)

    async def _base_request(self, path: str, param: str = ''):
        """
        请求并解析RSS数据
        :param path:
        :param param:
        :return:
        """
        url = (self.__base_url or "") + path
        should_close = False
        client = self.__client

        if not client:
            client = httpx.AsyncClient()
            should_close = True

        try:
            response = await client.get(url)
            if response.status_code != 200:
                raise ValueError(f"请求失败，状态码: {response.status_code}, 错误信息: {response.text}")

            # 检查响应内容类型
            content_type = response.headers.get('content-type', '')

            try:
                if 'application/json' in content_type:
                    # JSON格式响应
                    data = response.json()
                    return [RssResponse(**item) for item in data]
                else:
                    # 默认尝试解析为XML
                    return self._parse_rss_xml(response.text)
            except Exception as e:
                raise ValueError(f"解析响应失败: {e}")
        except Exception as e:
            # 发送失败会由外部捕获，发送tg通知
            raise ValueError(f"请求失败: {e}")
        finally:
            if should_close:
                await client.aclose()

    async def get_x_rss_by_user_media(self, user_id: str):
        """
        获取指定用户发布的含媒体推文
        :param user_id:
        :return:
        """
        return await self._base_request(path=f"/twitter/media/{user_id}")

    def _parse_rss_xml(self, xml_content: str) -> list[RssResponse]:
        root = ET.fromstring(xml_content)
        items = []

        # 查找所有的item节点
        for item in root.findall('.//item'):
            # 提取各个字段
            title_elem = item.find('title')
            title = title_elem.text if title_elem is not None and title_elem.text else ""

            description_elem = item.find('description')
            description = description_elem.text if description_elem is not None and description_elem.text else ""

            link_elem = item.find('link')
            link = link_elem.text if link_elem is not None and link_elem.text else ""

            guid_elem = item.find('guid')
            guid = guid_elem.text if guid_elem is not None and guid_elem.text else ""

            # 获取isPermaLink属性
            is_perma_link = False
            if guid_elem is not None and 'isPermaLink' in guid_elem.attrib:
                is_perma_link = guid_elem.attrib['isPermaLink'].lower() == 'true'

            pub_date_elem = item.find('pubDate')
            pub_date = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""

            author_elem = item.find('author')
            author = author_elem.text if author_elem is not None and author_elem.text else ""

            # 创建RssResponse对象
            rss_item = RssResponse(
                title=title,
                description=description,
                link=link,
                guid=guid,
                isPermaLink=is_perma_link,
                pubDate=pub_date,
                author=author
            )
            items.append(rss_item)

        return items

async def test():
    """测试RSS客户端功能"""
    async with RssClient("http://111.228.35.180:1200") as rss_client:
        media = await rss_client.get_x_rss_by_user_media("Chung_hwani")
        print(f"获取到 {len(media)} 条推文")
        for i, item in enumerate(media[:3]):  # 只显示前3条
            print(f"\n--- 推文 {i+1} ---")
            print(f"标题: {item.title}")
            print(f"作者: {item.author}")
            print(f"内容: {item.description}")
            print(f"GUID: {item.guid}")
            print(f"原始发布时间: {item.pubDate}")
            print(f"解析后时间: {item.pubDatetime}")
            print(f"链接: {item.link}")

if __name__ == '__main__':
    # 运行异步测试
    asyncio.run(test())