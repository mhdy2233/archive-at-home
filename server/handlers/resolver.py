import re

from loguru import logger
from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from utils.db import User, deduct_GP, get_current_GP
from utils.resolve import destroy_url, get_download_url, get_gallery_info


async def resolve_gallery_by_url(
    update: Update, context: ContextTypes.DEFAULT_TYPE, url: str
):
    msg = await update.effective_message.reply_text("🔍 正在解析画廊信息...")
    logger.info(f"解析画廊 {url}")

    try:
        text, thumb, gid, token, user_GP_cost, require_GP = await get_gallery_info(url)
    except Exception as e:
        await msg.edit_text("❌ 画廊解析失败，请检查链接或稍后再试")
        logger.error(f"画廊 {url} 解析失败：{e}")
        return

    keyboard = [
        [InlineKeyboardButton("🌐 跳转画廊", url=url)],
        (
            [
                InlineKeyboardButton(
                    "📦 归档下载",
                    callback_data=f"download|{gid}|{token}|{1 if require_GP else 0}|{user_GP_cost}",
                )
            ]
            if update.effective_chat.type == "private"
            else [
                InlineKeyboardButton(
                    "🤖 在 Bot 中打开",
                    url=f"https://t.me/{context.application.bot_username}?start={gid}_{token}",
                )
            ]
        ),
    ]

    await msg.delete()
    await update.effective_message.reply_photo(
        photo=thumb, caption=text, reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def resolve_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.effective_message.text.strip()
    await resolve_gallery_by_url(update, context, url)


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = await User.get_or_none(id=update.effective_user.id).prefetch_related(
        "GP_records"
    )

    if not user:
        await update.effective_message.reply_text("📌 请先使用 /start 注册")
        return

    if user.group == "黑名单":
        await update.effective_message.reply_text("🚫 您已被封禁")
        return

    _, gid, token, require_GP, user_GP_cost = query.data.split("|")
    user_GP_cost = int(user_GP_cost)

    current_GP = await get_current_GP(user)
    if current_GP < user_GP_cost:
        await update.effective_message.reply_text(f"⚠️ GP 不足，当前余额：{current_GP}")
        return

    caption = re.sub(
        r"(\n\n)?(🗑 已销毁链接|❌ 下载链接获取失败，请稍后再试)$",
        "",
        update.effective_message.caption,
    )

    await update.effective_message.edit_caption(
        caption=f"{caption}\n\n⏳ 正在获取下载链接，请稍等...",
        reply_markup=update.effective_message.reply_markup,
    )
    logger.info(f"获取 https://e-hentai.org/g/{gid}/{token}/ 下载链接")

    d_url, client = await get_download_url(user, gid, token, require_GP == "1")
    if d_url:
        await deduct_GP(user, user_GP_cost)
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🌐 跳转画廊", url=f"https://e-hentai.org/g/{gid}/{token}/"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔗 复制下载链接", copy_text=CopyTextButton(d_url)
                    ),
                    InlineKeyboardButton("📥 跳转下载", url=d_url),
                ],
                [
                    InlineKeyboardButton(
                        "🗑 销毁链接",
                        callback_data=f"destroy|{gid}|{token}|{require_GP}|{user_GP_cost}|{client.id}",
                    )
                ],
            ]
        )

        await update.effective_message.edit_caption(
            caption=f"{caption}\n\n✅ 下载链接获取成功\n📡 节点提供者：{client.provider.name}",
            reply_markup=keyboard,
        )
    else:
        await update.effective_message.edit_caption(
            caption=f"{caption}\n\n❌ 下载链接获取失败，请稍后再试",
            reply_markup=update.effective_message.reply_markup,
        )
        logger.error(f"https://e-hentai.org/g/{gid}/{token}/ 下载链接获取失败")


async def destroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, gid, token, require_GP, user_GP_cost, client_id = query.data.split("|")

    await destroy_url(gid, token, client_id)

    caption = re.sub(
        r"\n\n✅ 下载链接获取成功\n📡 节点提供者：.*$",
        "",
        update.effective_message.caption,
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🌐 跳转画廊", url=f"https://e-hentai.org/g/{gid}/{token}/"
                )
            ],
            [
                InlineKeyboardButton(
                    "📦 归档下载",
                    callback_data=f"download|{gid}|{token}|{require_GP}|{user_GP_cost}",
                )
            ],
        ]
    )

    await update.effective_message.edit_caption(
        caption=f"{caption}\n\n🗑 已销毁链接",
        reply_markup=keyboard,
    )
    logger.info(f"https://e-hentai.org/g/{gid}/{token}/ 下载链接已销毁")


def register(app):
    app.add_handler(
        MessageHandler(
            filters.Regex(r"https://e[-x]hentai.org/g/(\d+)/([a-f0-9]+)"),
            resolve_gallery,
        )
    )
    app.add_handler(CallbackQueryHandler(download, pattern=r"^download"))
    app.add_handler(CallbackQueryHandler(destroy, pattern=r"^destroy"))
