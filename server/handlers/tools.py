from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from utils.cookie import get_cookie

async def cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) != 2:
        await update.message.reply_text("该命令用于更新您的igneous, 目前后端有cf, 美国, 德国,罗马尼亚.\n命令格式为:\n/get_cookie ipb_member_id ipb_pass_hash\n如: /get_cookie 1234 xxxx")
    else:
        input1 = args[0]
        input2 = args[1]
        t = await update.message.reply_text("正在获取中...")
        text = await get_cookie(input1, input2)
        await t.edit_text(text, parse_mode="HTML")


def register(app):
    """注册命令处理器"""
    app.add_handler(CommandHandler("get_cookie", cookie))