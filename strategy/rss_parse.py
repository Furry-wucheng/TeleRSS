import asyncio
import html
import re
from typing import List

from utils.rss_client import RssClient
from strategy.context import TwitterContent
from utils.config_manager import get_config

class RssStrategy:
    """
    RSS策略类，负责从RSS源获取数据
    """
    def __init__(self):
        base_type = get_config("base", "type")
        if base_type != "rss":
             # 如果配置不是rss，理论上不应该初始化这个策略，或者这只是个备用
             pass

        self.base_url = get_config("rss", "rss_base_url")
        if not self.base_url:
            raise ValueError("RSS Base URL match be set in config [rss] rss_base_url")

        self.client = RssClient(self.base_url)

    async def get_new_media(self, user_id: str) -> List[TwitterContent]:
        """
        通过RSS获取用户新媒体内容
        :param user_id: 用户ID
        :return: TwitterContent列表
        """
        try:
            # 获取原始RSS数据
            raw_data = await self.client.get_x_rss_by_user_media(user_id)
        except Exception as e:
            # 这里捕获RSS客户端的错误，并向上抛出，或者在这里进行特定的日志记录
            # 为了让上层能够感知到是RSS错误，我们可以抛出一个自定义异常或者保留原异常
            raise RuntimeError(f"RSS fetch failed for user {user_id}: {str(e)}") from e

        result: List[TwitterContent] = []

        for item in raw_data:
            author = item.author
            description = item.description
            title = item.title
            date = item.pubDate
            link = item.link

            ## 正则提取所有视频（自动去除&后面的内容 -> 修正为完整URL）
            vedio_list = re.findall(r'<video[^>]*src=["\']([^"\']*)', description)
            vedio_list = [html.unescape(url) for url in vedio_list if url]

            ##正则提取img里面的所有链接（自动去除&后面的内容 -> 修正为完整URL）
            image_list = re.findall(r'<img[^>]*src=["\']([^"\']*)', description)
            image_list = [html.unescape(url) for url in image_list if url]

            ## 合并成列表
            media_list = vedio_list + image_list

            # 放入TwitterContent里面
            result.append(TwitterContent(author=author,content=description,link=link,publish_date=date,title=title,media_list=media_list))

        return result

async def test():
    try:
        strategy = RssStrategy()
        result = await strategy.get_new_media("Panda_inn1")
        print(result[:3])
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == '__main__':
    asyncio.run(test())