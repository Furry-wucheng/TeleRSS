from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
import model.follower_model as follower_model
from utils.logger import get_logger

logger = get_logger(__name__)


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


async def get_category_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gets the list of categories.
    """
    cate_list = await follower_model.get_all_category()
    await update.message.reply_text(f"当前分类列表为：{cate_list}")


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
    for cmd, callback in BOT_COMMANDS:
        application.add_handler(CommandHandler(cmd.command, callback))


async def setup_commands(application: Application, merge: bool = False):
    """
    通过 Telegram API 自动设置 Bot 菜单命令，无需在 BotFather 手动配置。
    """
    await application.bot.set_my_commands([cmd for cmd, _ in BOT_COMMANDS])
    logger.info("Bot commands menu has been set successfully.")
