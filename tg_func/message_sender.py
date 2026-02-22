import asyncio
import html

from strategy.strategy_factory import get_strategy
from utils.logger import get_logger
from utils.telegram_client import get_telegram_bot, get_target_chat_id
from telegram import Bot, InputMediaPhoto, InputMediaVideo
from strategy.context import TwitterContent

logger = get_logger(__name__)

async def send_twitter_content(bot: Bot, content: TwitterContent, target_chat_id: str, category: str = "Uncategorized", post_time: str = ""):
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
        await bot.send_message(chat_id=target_chat_id, text=msg, parse_mode="HTML")
        return

    # 构造媒体对象列表
    input_media_list = []

    for i, url in enumerate(media_list):
        # 非常粗糙的类型判断，实际应检查文件扩展名或Content-Type
        is_video = ".mp4" in url or "video" in url

        # 只有第一个媒体带这个caption
        # 且如果是媒体组，caption也只加一次。
        # PTB InputMedia supports caption on individual items.
        # But for sendMediaGroup, usually only the caption of the first item (or others) is displayed as the message caption.
        caption = msg if i == 0 else None

        if is_video:
            input_media_list.append(InputMediaVideo(media=url, caption=caption, parse_mode="HTML"))
        else:
            input_media_list.append(InputMediaPhoto(media=url, caption=caption, parse_mode="HTML"))

    try:
        if len(input_media_list) == 1:
            # 单个媒体
            media = input_media_list[0]
            if isinstance(media, InputMediaVideo):
                await bot.send_video(
                    chat_id=target_chat_id,
                    video=media.media,
                    caption=media.caption,
                    parse_mode="HTML"
                )
            else:
                await bot.send_photo(
                    chat_id=target_chat_id,
                    photo=media.media,
                    caption=media.caption,
                    parse_mode="HTML"
                )
        else:
            # 多个媒体，使用媒体组
            # Telegram 限制一次最多发送 10 个媒体
            # 如果超过10个，需要分批发送
            # 这里简单做一下切片，每10个一组
            chunk_size = 10
            for i in range(0, len(input_media_list), chunk_size):
                chunk = input_media_list[i : i + chunk_size]
                # If splitting into chunks, the second chunk won't have the caption if we only set it on the very first item (i=0 global).
                # That is generally desired behavior (not repeating the big text block).
                await bot.send_media_group(chat_id=target_chat_id, media=chunk)

    except Exception as e:
        logger.error(f"Failed to send media: {e}")
        # 如果发送媒体失败（例如格式不支持），尝试降级为只发送文本链接
        await bot.send_message(chat_id=target_chat_id, text=f"{msg}\n\n(媒体发送失败: {e})", parse_mode="HTML")


async def test():
    bot = get_telegram_bot()
    chat_id = get_target_chat_id()
    rss_client = get_strategy()
    result = await rss_client.get_new_media("yibian_sz")
    await send_twitter_content(bot, result[0], chat_id)


if __name__ == '__main__':
    asyncio.run(test())