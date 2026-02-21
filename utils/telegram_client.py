from __future__ import annotations

import asyncio
from typing import Any, Sequence
from telegram import Bot, InputMediaPhoto, InputMediaVideo

from utils.config_manager import ConfigError, get_config


class TelegramClient:
    """
    Telegram Bot API 客户端 (基于 python-telegram-bot)
    """
    _bot: Bot

    def __init__(self, token: str, *, timeout: float = 10.0) -> None:
        if not token:
            raise ValueError("Telegram token 不能为空")
        self._bot = Bot(token=token)

    @classmethod
    def create_from_config(cls, section: str = "telegram", option: str = "bot_token", **kwargs: Any) -> "TelegramClient":
        token = get_config(section, option, required=True)
        if not token:
            raise ConfigError(f"[{section}] {option} 未配置")
        return cls(token, **kwargs)

    async def close(self) -> None:
        # python-telegram-bot manages its own connection pool usually,
        # but if we need to explicitly close, we can look into it.
        pass

    async def __aenter__(self) -> "TelegramClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def send_message(self, chat_id: int | str, message: str, *, parse_mode: str = "HTML", disable_preview: bool = False) -> Any:
        return await self._bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_preview
        )

    async def send_photo(self, chat_id: int | str, photo: str | bytes, caption: str | None = None, *, parse_mode: str = "HTML") -> Any:
        return await self._bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode=parse_mode
        )

    async def send_video(self, chat_id: int | str, video: str | bytes, caption: str | None = None, *, parse_mode: str = "HTML", supports_streaming: bool = True) -> Any:
        return await self._bot.send_video(
            chat_id=chat_id,
            video=video,
            caption=caption,
            parse_mode=parse_mode,
            supports_streaming=supports_streaming
        )

    async def send_media_group(self, chat_id: int | str, media_list: Sequence[InputMediaPhoto | InputMediaVideo]) -> Any:
        return await self._bot.send_media_group(
            chat_id=chat_id,
            media=media_list
        )



async def test():
    client = TelegramClient.create_from_config()
    response = await client.send_video("856909568", "https://video.twimg.com/amplify_video/2023038552037326849/vid/avc1/1280x720/6nA4FTH3NrX-Dxtp.mp4?tag=14",)
    print(response)

if __name__ == '__main__':
    asyncio.run(test())