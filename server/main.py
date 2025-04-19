import threading

import uvicorn
from loguru import logger
from telegram.ext import Application

from config.config import cfg
from db.db import init_db
from handlers import BOT_COMMANDS, register_all_handlers
from utils.client import refresh_all_clients
from utils.resolve import fetch_tag_map

logger.add("log.log", encoding="utf-8")


async def post_init(app):
    app.bot_username = (await app.bot.get_me()).username
    await app.bot.set_my_commands(BOT_COMMANDS)


telegram_app = (
    Application.builder()
    .token(cfg["BOT_TOKEN"])
    .post_init(post_init)
    .proxy(cfg["proxy"])
    .build()
)

register_all_handlers(telegram_app)
telegram_app.job_queue.run_repeating(fetch_tag_map, interval=86400, first=5)
telegram_app.job_queue.run_once(init_db, 0, job_kwargs={"misfire_grace_time": 10})
telegram_app.job_queue.run_repeating(refresh_all_clients, interval=3600, first=10)


# 启动 FastAPI 的线程
def start_fastapi():
    uvicorn.run("utils.api:app", host=None, port=3028)


if __name__ == "__main__":
    threading.Thread(target=start_fastapi, daemon=True).start()
    telegram_app.run_polling()
