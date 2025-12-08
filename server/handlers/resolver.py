import re, html

from loguru import logger
from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from config.config import cfg
from db.db import User, Preview
from utils.GP_action import deduct_GP, get_current_GP
from utils.resolve import get_download_url, get_gallery_info
from utils.preview import task_list

async def reply_gallery_info(
    update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, gid: str, token: str
):
    msg = await update.effective_message.reply_text("🔍 正在解析画廊信息...")
    logger.info(f"解析画廊 {url}")

    try:
        text, has_spoiler, thumb, require_GP, timeout = await get_gallery_info(
            gid, token
        )
    except Exception as e:
        await msg.edit_text("❌ 画廊解析失败，请检查链接或稍后再试")
        logger.error(f"画廊 {url} 解析失败：{e}")
        return

    keyboard = [
        [InlineKeyboardButton("🌐 跳转画廊", url=url)],
    ]
    if update.effective_chat.type == "private":
        has_spoiler = False
        if require_GP['org']:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "📦 原图归档下载",
                        callback_data=f"download|{gid}|{token}|org|{require_GP['org']}|{timeout}",
                    ),
                ]
            )
            if require_GP['res']:
                keyboard[1].append(
                    InlineKeyboardButton(
                            "📦 重采样归档下载",
                            callback_data=f"download|{gid}|{token}|res|{require_GP['res']}|{timeout}",
                        ),
                )
        else:
            keyboard[0].append(
                InlineKeyboardButton(
                        "📦 不支持归档", url=url
                    ),
            )
        if require_GP['res']:
            keyboard[1].append(InlineKeyboardButton("生成预览(实验性)", callback_data=f"preview|{gid}|{token}|{require_GP['pre']}|{timeout}"))
        if cfg["AD"]["text"] and cfg["AD"]["url"]:
            keyboard.append(
                [InlineKeyboardButton(cfg["AD"]["text"], url=cfg["AD"]["url"])]
            )
    else:
        keyboard[0].append(
            InlineKeyboardButton(
                "🤖 在 Bot 中打开",
                url=f"https://t.me/{context.application.bot.username}?start={gid}_{token}",
            )
        )

    await msg.delete()
    try:
        await update.effective_message.reply_photo(
            photo=thumb,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            has_spoiler=has_spoiler,
            parse_mode="HTML",
        )
    except BadRequest as e:
        if "Media caption too long" in str(e) or "Message caption is too long" in str(e):
            # 特殊处理：caption 太长
            try:
                text, has_spoiler, thumb, require_GP, timeout = await get_gallery_info(
                    gid, token, long=True
                )
            except Exception as e:
                await update.effective_message.edit_text("❌ 画廊解析失败，请检查链接或稍后再试")
                logger.error(f"画廊 {url} 解析失败：{e}")
                return
            await update.effective_message.reply_photo(
            photo=thumb,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            has_spoiler=has_spoiler,
            parse_mode="HTML",
        )
        else:
            # 其他 BadRequest 异常继续抛出
            raise


async def resolve_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    url, gid, token = re.search(
        r"https://e[-x]hentai\.org/g/(\d+)/([0-9a-f]{10})", text
    ).group(0, 1, 2)
    await reply_gallery_info(update, context, url, gid, token)


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

    _, gid, token, image_quality, require_GP, timeout = query.data.split("|")

    current_GP = get_current_GP(user)
    if current_GP < int(require_GP):
        await update.effective_message.reply_text(f"⚠️ GP 不足，当前余额：{current_GP}")
        return

    caption = re.sub(
        r"\n\n❌ 下载链接获取失败，请稍后再试$",
        "",
        update.effective_message.caption,
    )
    await update.effective_message.edit_caption(
        caption=f"<blockquote expandable>{html.escape(caption)}</blockquote>\n\n⏳ 正在获取下载链接，请稍等...",
        reply_markup=update.effective_message.reply_markup,
        parse_mode="HTML",
    )
    logger.info(f"获取 https://e-hentai.org/g/{gid}/{token}/ 下载链接")

    d_url = await get_download_url(
        user, gid, token, image_quality, int(require_GP), timeout
    )
    if d_url:
        await deduct_GP(user, int(require_GP))
        keyboard = [
                [
                    InlineKeyboardButton(
                        "🌐 跳转画廊", url=f"https://e-hentai.org/g/{gid}/{token}/"
                    )
                ],
                []
            ]

        text = f"<blockquote expandable>{html.escape(caption)}</blockquote>\n✅ 下载链接获取成功\n<blockquote expandable>"
        if image_quality == "org":
            keyboard[1].append(InlineKeyboardButton("🔗 复制原图", copy_text=CopyTextButton(d_url+"0?start=1")))
            text+= f"原图: <code>{d_url}0?start=1</code>\n"
        keyboard[1].append(InlineKeyboardButton("🔗 复制重采样", copy_text=CopyTextButton(d_url+"1?start=1")))
        text+= f"重采样: <code>{d_url}1?start=1</code></blockquote>"
        if cfg["AD"]["text"] and cfg["AD"]["url"]:
            keyboard.append([InlineKeyboardButton(cfg["AD"]["text"], url=cfg["AD"]["url"])])
        await update.effective_message.edit_caption(
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
    elif d_url == None:
        await update.effective_message.edit_caption(
            caption=f"{html.escape(caption)}\n\n❌ 暂无可用服务器",
            reply_markup=update.effective_message.reply_markup,
            parse_mode="HTML",
        )
        logger.error(f"https://e-hentai.org/g/{gid}/{token}/ 下载链接获取失败")
    else:
        await update.effective_message.edit_caption(
            caption=f"{html.escape(caption)}\n\n❌ 获取下载链接失败",
            reply_markup=update.effective_message.reply_markup,
            parse_mode="HTML",
        )
        logger.error(f"https://e-hentai.org/g/{gid}/{token}/ 下载链接获取失败")

async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    _, gid, token, require_GP, timeout = query.data.split("|")
    ph_url = await Preview.filter(gid=gid).first()
    if ph_url:
        await update.effective_message.reply_text(f"已存在预览，本次不消耗GP\n{ph_url.ph_url}")
    else:
        current_GP = get_current_GP(user)
        if current_GP < int(require_GP):
            await update.effective_message.reply_text(f"⚠️ GP 不足，当前余额：{current_GP}")
            return
        
        for x in task_list:
            if x['gid'] == gid:
                mes = await update.effective_message.reply_text(f"已有相同任务, 请稍候重试(队列: {task_list.index({"mes": mes,"gid": gid,"token": token,"user": user})})")
                return

        mes = await update.effective_message.reply_text(f"已成功加入队列({len(task_list)})...")
        task_list.append({
            "mes": mes,
            "gid": gid,
            "token": token,
            "user": user
        })

def register(app):
    app.add_handler(
        MessageHandler(
            filters.Regex(r"https://e[-x]hentai\.org/g/\d+/[0-9a-f]{10}"),
            resolve_gallery,
        )
    )
    app.add_handler(CallbackQueryHandler(download, pattern=r"^download"))
    app.add_handler(CallbackQueryHandler(preview, pattern=r"^preview"))
