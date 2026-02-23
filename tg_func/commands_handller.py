from functools import wraps
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
import model.follower_model as follower_model
from utils.config_manager import get_config
from utils.logger import get_logger

logger = get_logger(__name__)


def admin_only(func):
    """装饰器：限制命令只能由配置的 admin_chat_id 使用。未配置时拒绝所有命令。"""
    admin_chat_id = get_config("telegram", "admin_chat_id")
    admin_id = str(admin_chat_id).strip() if admin_chat_id else None


    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        sender_id = str(update.effective_user.id)
        if admin_id is None:
            logger.warning(f"命令 /{func.__name__} 被拒绝: admin_chat_id 未配置，拒绝 user_id={sender_id}")
            await update.message.reply_text("⛔ 该功能未启用，请联系管理员配置 admin_chat_id。")
            return
        if sender_id != admin_id:
            logger.warning(f"未授权访问: user_id={sender_id} 尝试执行 /{func.__name__}")
            await update.message.reply_text("⛔ 权限不足，您无权执行此命令。")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def add_new_userid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Adds a new user ID to the database.
    """
    logger.info("Received addid command.")
    args = context.args

    if len(args) == 0 or len(args) > 3:
        await update.message.reply_text("Usage: /add_id <user_id> [category] [source]")
        return

    user_id = args[0]

    if len(args) == 1:
        await follower_model.add_new_follower(user_id)
    elif len(args) == 2:
        await follower_model.add_new_follower(user_id, args[1])
    elif len(args) == 3:
        await follower_model.add_new_follower(user_id, args[1], args[2])
    else:
        await update.message.reply_text("错误！请检查输入参数")


@admin_only
async def remove_userid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Removes a user ID from the database.
    """
    logger.info("Received removeid command.")
    args = context.args

    if len(args) != 1:
        await update.message.reply_text("Usage: /remove_id <user_id>")
        return

    user_id = args[0]
    await follower_model.delete_follower(user_id)


@admin_only
async def update_userid_cate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Updates the category of a user ID.
    """
    logger.info("Received updateidcate command.")
    args = context.args

    if len(args) != 2:
        await update.message.reply_text("Usage: /update_id_cate <user_id> <category>")
        return

    user_id = args[0]
    category = args[1]
    await follower_model.update_follower(user_id, category)


@admin_only
async def get_category_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gets the list of categories.
    """
    cate_list = await follower_model.get_all_category()
    await update.message.reply_text(f"当前分类列表为：{cate_list}")


@admin_only
async def get_disable_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gets the list of disabled IDs.
    """
    disable_id = await follower_model.select_follower_by_category("disable")
    text = ", ".join([f"{id}" for id in disable_id])
    await update.message.reply_text(f"当前禁用列表为：{text}")


# 新增命令只需在这里加一行，注册和菜单自动同步
BOT_COMMANDS = [
    (BotCommand("add_id", "添加关注用户 <user_id> [category] [source]"), add_new_userid),
    (BotCommand("remove_id", "删除关注用户 <user_id>"), remove_userid),
    (BotCommand("update_id_cate", "更新用户分类 <user_id> <category>"), update_userid_cate),
    (BotCommand("get_cate_list", "获取所有分类列表"), get_category_list),
    (BotCommand("get_disable_id", "获取所有禁用用户"), get_disable_id),
]


def register_handlers(application: Application):
    admin_chat_id = get_config("telegram", "admin_chat_id")
    if not admin_chat_id or not str(admin_chat_id).strip():
        logger.warning("⚠️  admin_chat_id 未配置！所有 Bot 命令将对任何用户拒绝执行，请在配置文件或环境变量中设置 admin_chat_id。")
    else:
        logger.info(f"✅ Bot 命令权限已启用，管理员 Chat ID: {str(admin_chat_id).strip()}")

    for cmd, callback in BOT_COMMANDS:
        application.add_handler(CommandHandler(cmd.command, callback))


async def setup_commands(application: Application, merge: bool = False):
    """
    通过 Telegram API 自动设置 Bot 菜单命令，无需在 BotFather 手动配置。
    """
    await application.bot.set_my_commands([cmd for cmd, _ in BOT_COMMANDS])
    logger.info("Bot commands menu has been set successfully.")
