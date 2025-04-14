import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from tortoise.functions import Count

from handlers.resolver import resolve_gallery_by_url
from utils.db import GPRecord, User, get_current_GP


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


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理每日签到命令"""
    user = await User.get_or_none(
        id=update.effective_message.from_user.id
    ).prefetch_related("GP_records")
    if not user:
        await update.effective_message.reply_text("请先使用 /start 注册")
        return

    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    already_checked = any(
        record.source == "签到"
        and record.expire_time.astimezone(ZoneInfo("Asia/Shanghai")).date()
        == today + timedelta(days=7)
        for record in user.GP_records
    )

    if already_checked:
        await update.effective_message.reply_text("📌 你今天已经签过到了~")
        return

    original_balance = await get_current_GP(user)
    amount = random.randint(15000, 40000)
    await GPRecord.create(user=user, amount=amount)

    await update.effective_message.reply_text(
        f"✅ 签到成功！获得 {amount} GP！\n"
        f"💰 当前余额：{original_balance + amount} GP\n"
        f"⚠️ 注意：签到获得的 GP 有效期为 7 天"
    )
    logger.info(f"{user.name}（{user.id}）签到成功，获得 {amount} GP")


async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await update.effective_message.reply_text(
        f"🧾 用户组：{user.group}\n📊 使用次数：{user.history_count} 次\n💰 剩余 GP：{current_GP}"
    )


def register(app):
    """注册命令处理器"""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("myinfo", my_info))
