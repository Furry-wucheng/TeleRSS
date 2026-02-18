import asyncio
import html
from typing import List

from strategy.strategy_factory import get_strategy
from utils.config_manager import get_config
from utils.telegram_client import TelegramClient, TelegramMedia
from strategy.context import TwitterContent

async def send_twitter_content(client: TelegramClient, content: TwitterContent, target_chat_id: str, category: str = "Uncategorized", post_time: str = ""):
    """
    发送推特内容到Telegram
    根据媒体数量自动选择发送单张图片/视频还是媒体组
    """

    # 如果原文链接里面有tg不符合要求的字符，需要进行解析
    safe_author = html.escape(content.author)
    safe_title = html.escape(content.title)

    # 构造消息头部，支持 #category 和 @author 以及时间
    header = f'@{safe_author}  #{category}'
    if post_time:
        header += f'  <i>{post_time}</i>'

    msg = f'{header}\n{safe_title}\n<a href="{content.link}">源链接</a>'

    media_list = content.media_list
    if not media_list:
        # 无媒体，仅发送文本
        await client.send_message(target_chat_id, msg)
        return

    # 构造媒体对象列表
    tg_media_list: List[TelegramMedia] = []

    for i, url in enumerate(media_list):
        # 非常粗糙的类型判断，实际应检查文件扩展名或Content-Type
        is_video = ".mp4" in url or "video" in url

        # 只有第一个媒体带这个caption
        caption = msg if i == 0 else None

        if is_video:
            tg_media_list.append(TelegramMedia.video(url, caption=caption))
        else:
            tg_media_list.append(TelegramMedia.photo(url, caption=caption))

    try:
        if len(tg_media_list) == 1:
            # 单个媒体
            media = tg_media_list[0]
            if media.media_type == "video":
                await client.send_video(target_chat_id, media.media, caption=media.caption)
            else:
                await client.send_photo(target_chat_id, media.media, caption=media.caption)
        else:
            # 多个媒体，使用媒体组
            # Telegram 限制一次最多发送 10 个媒体
            # 如果超过10个，需要分批发送
            # 这里简单做一下切片，每10个一组
            chunk_size = 10
            for i in range(0, len(tg_media_list), chunk_size):
                chunk = tg_media_list[i : i + chunk_size]
                # 注意：媒体组的 caption 只能附在第一个媒体上
                # 分组后，如果第一组有caption，后续组通常没有，或者需要重新把链接附在某处？
                # 这里只保留第一组的caption（上面的循环已经处理了 caption=msg if i==0）
                # 但是如果第一组发完了，第二组就没有链接信息了。
                # 简单起见，我们不在第二组重复发 caption，防止刷屏。
                await client.send_media_group(target_chat_id, chunk)

    except Exception as e:
        print(f"Failed to send media: {e}")
        # 如果发送媒体失败（例如格式不支持），尝试降级为只发送文本链接
        await client.send_message(target_chat_id, f"{msg}\n\n(媒体发送失败: {e})")


async def test():
    tg_client = TelegramClient.create_from_config()
    chat_id = get_config("telegram", "target_chat_id")
    rss_client = get_strategy()
    result = await rss_client.get_new_media("yibian_sz")
    await send_twitter_content(tg_client, result[0], chat_id)


if __name__ == '__main__':
    asyncio.run(test())