from __future__ import annotations

from telegram import Bot
from telegram.ext import Application

from utils.config_manager import ConfigError, get_config
from utils.logger import get_logger

logger = get_logger(__name__)

_application_instance: Application | None = None
_target_chat_id: str | int | None = None


def get_telegram_bot() -> Bot:
    """
    Returns a singleton python-telegram-bot Bot instance from the Application.
    """
    return get_telegram_application().bot


def get_telegram_application() -> Application:
    """
    Returns a singleton python-telegram-bot Application instance.
    """
    global _application_instance
    if _application_instance is None:
        token = get_config("telegram", "bot_token", required=True)
        if not token:
            raise ConfigError("[telegram] bot_token 未配置")

        # Build the application with the token directly.
        # This creates the Bot and the Updater.
        _application_instance = Application.builder().token(token).build()

        # 注册 handlers
        # 为了避免循环引用，在这里导入 handlers
        from tg_func.commands_handller import register_handlers
        register_handlers(_application_instance)

    return _application_instance


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
        logger.error(f"Failed to send error notification: {e}")
