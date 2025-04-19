import uuid

from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes
from tortoise.functions import Count

from db.db import User
from handlers.resolver import resolve_gallery_by_url
from utils.GP_action import checkin, get_current_GP


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 注册及跳转解析命令"""
    tg_user = update.effective_message.from_user
    user, created = await User.get_or_create(id=tg_user.id, name=tg_user.full_name)

    if created:
        await update.effective_message.reply_text("🎉 欢迎加入，您已成功注册！")
        logger.info(f"{user.name}（{user.id}）注册成功")
    if context.args:
        gid, token = context.args[0].split("_")
        await resolve_gallery_by_url(
            update, context, f"https://e-hentai.org/g/{gid}/{token}/"
        )
    elif not created:
        await update.effective_message.reply_text("✅ 您已经注册过了~")


async def checkin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理每日签到命令"""
    user = await User.get_or_none(
        id=update.effective_message.from_user.id
    ).prefetch_related("GP_records")
    if not user:
        await update.effective_message.reply_text("请先使用 /start 注册")
        return

    amount, balance = await checkin(user)

    if not amount:
        await update.effective_message.reply_text("📌 你今天已经签过到了~")
        return

    await update.effective_message.reply_text(
        f"✅ 签到成功！获得 {amount} GP！\n"
        f"💰 当前余额：{balance} GP\n"
        f"⚠️ 注意：签到获得的 GP 有效期为 7 天"
    )


async def myinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看我的账户信息"""
    user = (
        await User.annotate(history_count=Count("archive_histories"))
        .prefetch_related("GP_records")
        .get_or_none(id=update.effective_message.from_user.id)
    )
    if not user:
        await update.effective_message.reply_text("请先使用 /start 注册")
        return

    current_GP = await get_current_GP(user)
    text = f"🧾 用户组：{user.group}\n📊 使用次数：{user.history_count} 次\n💰 剩余 GP：{current_GP}"

    if update.effective_chat.type == "private":
        text += f"\nAPI Key：`{user.apikey}`"
        keyboard = [
            [InlineKeyboardButton("重置 API Key", callback_data="reset_apikey")]
        ]
        await update.effective_message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="MarkdownV2"
        )
    else:
        await update.effective_message.reply_text(text)


async def reset_apikey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = await User.get(id=user_id)
    user.apikey = str(uuid.uuid4())
    await user.save()

    await query.edit_message_text(
        f"重置成功\nAPI Key：`{user.apikey}`", parse_mode="MarkdownV2"
    )


def register(app):
    """注册命令处理器"""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin_handler))
    app.add_handler(CommandHandler("myinfo", myinfo))
    app.add_handler(CallbackQueryHandler(reset_apikey, pattern=r"^reset_apikey$"))
