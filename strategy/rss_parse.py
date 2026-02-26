import asyncio
import html
import re
from typing import List

from utils.rss_client import RssClient
from strategy.context import TwitterContent
from utils.config_manager import get_config
from utils.logger import get_logger

logger = get_logger(__name__)

class RssStrategy:
    """
    RSS策略类，负责从RSS源获取数据
    """
    def __init__(self):
        base_type = get_config("base", "type", fallback="rss")
        if base_type != "rss":
             # 如果配置不是rss，理论上不应该初始化这个策略，或者这只是个备用
             pass

        self.base_url = get_config("rss", "rss_base_url", required=True)
        self.client = RssClient(self.base_url)

    async def get_new_media(self, user_id: str, retry_count: int = 3, retry_interval: float = 5) -> List[TwitterContent]:
        """
        通过RSS获取用户新媒体内容，失败时自动重试
        :param user_id: 用户ID
        :param retry_count: 最大重试次数
        :param retry_interval: 每次重试间隔（秒）
        :return: TwitterContent列表
        """
        for attempt in range(retry_count):
            try:
                # 获取原始RSS数据
                raw_data = await self.client.get_x_rss_by_user_media(user_id)
                break
            except Exception as e:
                if attempt < retry_count - 1:
                    logger.warning(f"RSS fetch failed for {user_id}, retrying ({attempt + 1}/{retry_count})... Error: {e}")
                    await asyncio.sleep(retry_interval)
                else:
                    raise RuntimeError(f"RSS fetch failed for user {user_id} after {retry_count} attempts: {str(e)}") from e
        else:
            raw_data = []

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
        result = await strategy.get_new_media("qigiu")
        logger.info(result[:3])
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == '__main__':
    asyncio.run(test())