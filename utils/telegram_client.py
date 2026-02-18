from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import httpx

from utils.config_manager import ConfigError, get_config

_API_BASE = "https://api.telegram.org"


class TelegramApiError(RuntimeError):
    """Raised when Telegram Bot API responds with a failure."""

    def __init__(self, method: str, payload: Mapping[str, Any], response: Mapping[str, Any]):
        super().__init__(f"Telegram API '{method}' 调用失败: {response}")
        self.method = method
        self.payload = payload
        self.response = response


class TelegramClient:
    """
    Telegram Bot API 客户端
    说明：发送的时候请构造符合要求的message（默认html）和mediaList
    """
    _token: str

    def __init__(self, token: str, *, timeout: float = 10.0) -> None:
        if not token:
            raise ValueError("Telegram token 不能为空")
        self._token = token
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = httpx.AsyncClient(
            base_url=f"{_API_BASE}/bot{token}", timeout=timeout
        )

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("TelegramClient 已关闭")
        return self._client

    @classmethod
    def create_from_config(cls, section: str = "telegram", option: str = "bot_token", **kwargs: Any) -> "TelegramClient":
        token = get_config(section, option, required=True)
        if not token:
            raise ConfigError(f"[{section}] {option} 未配置")
        return cls(token, **kwargs)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "TelegramClient":
        self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def send_message(self, chat_id: int | str, message: str, *, parse_mode: str = "HTML", disable_preview: bool = False) -> Mapping[str, Any]:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        }
        return await self._request("sendMessage", payload)

    async def send_photo(self, chat_id: int | str, photo: str | bytes, caption: str | None = None, *, parse_mode: str = "HTML") -> Mapping[str, Any]:
        payload = {"chat_id": chat_id, "parse_mode": parse_mode}
        if caption:
            payload["caption"] = caption
            
        if isinstance(photo, (bytes, bytearray)):
            return await self._request("sendPhoto", payload, files={"photo": ("photo.jpg", photo)})
        else:
            payload["photo"] = photo
            return await self._request("sendPhoto", payload)

    async def send_video(self, chat_id: int | str, video: str | bytes, caption: str | None = None, *, parse_mode: str = "HTML", supports_streaming: bool = True) -> Mapping[str, Any]:
        payload = {
            "chat_id": chat_id,
            "parse_mode": parse_mode,
            "supports_streaming": supports_streaming,
        }
        if caption:
            payload["caption"] = caption
            
        if isinstance(video, (bytes, bytearray)):
            files = {"video": ("video.mp4", video)}
            return await self._request("sendVideo", payload, files=files)
        else:
            payload["video"] = video
            return await self._request("sendVideo", payload)

    async def send_media_group(self, chat_id: int | str, media_list: Sequence["TelegramMedia"] | Iterable["TelegramMedia"]) -> Mapping[str, Any]:
        payload_list = [item.to_payload() for item in media_list]
        if not payload_list:
            raise ValueError("media_list 不能为空")
        payload = {"chat_id": chat_id, "media": payload_list}
        return await self._request("sendMediaGroup", payload)

    async def _request(self, method: str, payload: Mapping[str, Any], files: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        client = self._ensure_client()
        
        if files:
            # multipart/form-data upload
            data = {k: str(v) if v is not None else v for k, v in payload.items()}
            response = await client.post(f"/{method}", data=data, files=files)
        else:
            response = await client.post(f"/{method}", json=payload)

        try:
            data = response.json()
        except ValueError:
            # Not JSON, so probably a serious server error or network issue
            response.raise_for_status()
            raise TelegramApiError(method, payload, {"error": "Invalid JSON response", "status": response.status_code, "text": response.text})

        if not data.get("ok"):
             # This will catch 400 Bad Request with "ok": false and "description": "..."
            raise TelegramApiError(method, payload, data)

        return data


@dataclass(slots=True)
class TelegramMedia:
    """Helper for constructing media payloads for sendMediaGroup calls."""

    media_type: str
    media: str
    caption: str | None = None
    parse_mode: str = "HTML"
    extra: Mapping[str, Any] | None = None

    def to_payload(self) -> Mapping[str, Any]:
        if not self.media_type:
            raise ValueError("media_type 不能为空")
        if not self.media:
            raise ValueError("media 不能为空")

        payload: dict[str, Any] = {
            "type": self.media_type,
            "media": self.media,
        }
        if self.caption:
            payload["caption"] = self.caption
            payload["parse_mode"] = self.parse_mode
        if self.extra:
            payload.update(self.extra)
        return payload

    @classmethod
    def photo(cls, media: str, *, caption: str | None = None, parse_mode: str = "HTML", **extra: Any) -> "TelegramMedia":
        return cls("photo", media, caption=caption, parse_mode=parse_mode, extra=extra or None)

    @classmethod
    def video(cls, media: str, *, caption: str | None = None, parse_mode: str = "HTML", supports_streaming: bool = True, **extra: Any) -> "TelegramMedia":
        extra_payload = {"supports_streaming": supports_streaming}
        extra_payload.update(extra)
        return cls("video", media, caption=caption, parse_mode=parse_mode, extra=extra_payload)

async def test():
    client = TelegramClient.create_from_config()
    response = await client.send_video("856909568", "https://video.twimg.com/amplify_video/2023038552037326849/vid/avc1/1280x720/6nA4FTH3NrX-Dxtp.mp4?tag=14",)
    print(response)

if __name__ == '__main__':
    asyncio.run(test())