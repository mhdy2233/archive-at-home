import re
import uuid

from loguru import logger
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultsButton,
    InputTextMessageContent,
    Update,
)
from telegram.ext import CallbackQueryHandler, ContextTypes, InlineQueryHandler, ChosenInlineResultHandler
from tortoise.functions import Count

from db.db import User
from utils.GP_action import checkin, GPRecord
from utils.resolve import get_gallery_info
from utils.preview import preview_add, task_list


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()

    button = InlineQueryResultsButton(text="到Bot查看更多信息", start_parameter="start")

    # 没输入时提示
    if not query:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "签到", callback_data=f"checkin|{update.effective_user.id}"
                    )
                ]
            ]
        )
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="请输入 eh/ex 链接以获取预览",
                input_message_content=InputTextMessageContent("请输入链接"),
            ),
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="我的信息（签到）",
                input_message_content=InputTextMessageContent("点击按钮进行签到"),
                description="签到并查看自己的信息",
                reply_markup=keyboard,
            ),
        ]

        await update.inline_query.answer(results, button=button, cache_time=0)
        return

    # 正则匹配合法链接（严格格式）
    pattern = r"^https://e[-x]hentai\.org/g/(\d+)/([0-9a-f]{10})/?$"
    match = re.match(pattern, query)
    if not match:
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="链接格式错误",
                input_message_content=InputTextMessageContent("请输入合法链接"),
            )
        ]
        await update.inline_query.answer(results, cache_time=0)
        return

    gid, token = match.groups()

    logger.info(f"解析画廊 {query}")
    try:
        text, _, thumb, require_GP, _ = await get_gallery_info(gid, token)
    except:
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="获取画廊信息失败",
                input_message_content=InputTextMessageContent("请检查链接或稍后再试"),
            )
        ]
        await update.inline_query.answer(results, cache_time=0)
        return

    # 按钮
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌐 跳转画廊", url=query),
                InlineKeyboardButton(
                    "🤖 在 Bot 中打开",
                    url=f"https://t.me/{context.application.bot.username}?start={gid}_{token}",
                ),
            ],
        ]
    )

    results = [
        InlineQueryResultPhoto(
            id="info",
            photo_url=thumb,
            thumbnail_url=thumb,
            title="画廊预览",
            description="查看画廊预览图以及标签",
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        ),
        InlineQueryResultArticle(
            id=f"pre_{gid}_{token}_{require_GP['pre']}",
            thumbnail_url="https://www.emojiall.com/images/60/emojione/1F56E.png",
            title="生成预览",
            description="生成telegraph文章",
            input_message_content=InputTextMessageContent("请等待..."),
        )
    ]

    await update.inline_query.answer(results, cache_time=0)

async def result_pre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chosen_inline_result
    inline_message_id = result.inline_message_id
    user = result.from_user
    _, gid, token, require_GP = result.result_id.split("_")
    
    if inline_message_id:
        user = await User.get_or_none(id=user.id).prefetch_related(
            "GP_records"
        )

        if not user:
            user, created = await User.create(id=user.id, name=user.full_name)
            await GPRecord.create(user=user, amount=20000)

        if user.group == "黑名单":
            mes = "🚫 您已被封禁"
        else:
            if require_GP != None:
                result = await preview_add(gid, token, require_GP, user)
                mes = result['mes'] if result['status'] == True else f"已成功加入队列({len(task_list)})..."
                await context.bot.edit_message_text(
                    text=mes,
                    inline_message_id=inline_message_id
                )
                if not result['status']:
                    task_list.append({
                        "mes": inline_message_id,
                        "gid": gid,
                        "token": token,
                        "user": user
                    })
            else:

                mes = "没有重彩样，无法生成预览"
                await context.bot.edit_message_text(
                    text=mes,
                    inline_message_id=inline_message_id
                )

async def handle_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    user_id = update.effective_user.id
    if user_id != int(query.data.split("|")[1]):
        await query.answer("是你的东西吗？你就点！")
        return
    await query.answer()

    user = (
        await User.annotate(history_count=Count("archive_histories"))
        .prefetch_related("GP_records")
        .get_or_none(id=user_id)
    )
    if not user:
        keyboard = [
            [
                InlineKeyboardButton(
                    "🤖 打开 Bot",
                    url=f"https://t.me/{context.application.bot.username}?start",
                )
            ]
        ]

        await query.edit_message_text(
            "请先注册", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    amount, balance = await checkin(user)

    text = (
        f"✅ 签到成功！获得 {amount} GP！\n"
        if amount
        else "📌 你今天已经签过到了~\n"
        f"💰 当前余额：{balance} GP\n"
        f"📊 使用次数：{user.history_count} 次"
    )
    await query.edit_message_text(text)


def register(app):
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CallbackQueryHandler(handle_checkin, pattern=r"^checkin"))
    app.add_handler(ChosenInlineResultHandler(result_pre, pattern=r"^pre"))