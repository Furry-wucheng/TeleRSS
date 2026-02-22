from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
import model.follower_model as follower_model
from utils.logger import get_logger

logger = get_logger(__name__)

BOT_COMMANDS = [
    BotCommand("add_id", "添加关注用户 <user_id> [category] [source]"),
    BotCommand("remove_id", "删除关注用户 <user_id>"),
    BotCommand("update_id_cate", "更新用户分类 <user_id> <category>"),
    BotCommand("get_cate_list", "获取所有分类列表"),
]


async def add_new_userid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Adds a new user ID to the database.
    """
    args = context.args

    if len(args) == 0 or len(args) > 3:
        await update.message.reply_text("Usage: /addid <user_id> [category] [source]")
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
    args = context.args

    if len(args) != 1:
        await update.message.reply_text("Usage: /removeid <user_id>")
        return

    user_id = args[0]
    await follower_model.delete_follower(user_id)

async def update_userid_cate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Updates the category of a user ID.
    """
    args = context.args

    if len(args) != 2:
        await update.message.reply_text("Usage: /updateidcate <user_id> <category>")
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


def register_handlers(application: Application):
    """
    Registers handlers to the application.
    """
    application.add_handler(CommandHandler("addid", add_new_userid))
    application.add_handler(CommandHandler("removeid", remove_userid))
    application.add_handler(CommandHandler("updateidcate", update_userid_cate))
    application.add_handler(CommandHandler("getcategorylist", get_category_list))


async def setup_commands(application: Application):
    """
    通过 Telegram API 自动设置 Bot 菜单命令，无需在 BotFather 手动配置。
    """
    await application.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands menu has been set successfully.")