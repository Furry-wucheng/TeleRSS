from __future__ import annotations

from telegram import Bot

from utils.config_manager import ConfigError, get_config

_bot_instance: Bot | None = None
_target_chat_id: str | int | None = None


def get_telegram_bot() -> Bot:
    """
    Returns a singleton python-telegram-bot Bot instance.
    """
    global _bot_instance
    if _bot_instance is None:
        token = get_config("telegram", "bot_token", required=True)
        if not token:
            raise ConfigError("[telegram] bot_token 未配置")
        _bot_instance = Bot(token=token)
    return _bot_instance


def get_target_chat_id() -> str | int:
    """
    Returns the singleton target chat ID from config.
    """
    global _target_chat_id
    if _target_chat_id is None:
        _target_chat_id = get_config("telegram", "target_chat_id")
    return _target_chat_id


async def send_error_notification(bot: Bot, message: str):
    """
    发送错误通知给管理员
    """
    try:
        target_chat_id = get_target_chat_id()
        if target_chat_id:
            await bot.send_message(
                chat_id=target_chat_id,
                text=f"⚠️ <b>系统错误警告</b>\n{message}",
                parse_mode="HTML",
            )
    except Exception as e:
        print(f"Failed to send error notification: {e}")
