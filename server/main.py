from loguru import logger
from telegram.ext import Application

import utils.db as db
from config.config import cfg
from handlers import BOT_COMMANDS, register_all_handlers
from utils.client import refresh_all_clients

logger.add("log.log", encoding="utf-8")


async def post_init(app):
    app.bot_username = (await app.bot.get_me()).username
    await app.bot.set_my_commands(BOT_COMMANDS)


app = (
    Application.builder()
    .token(cfg["BOT_TOKEN"])
    .post_init(post_init)
    .proxy(cfg["proxy"])
    .build()
)
register_all_handlers(app)

app.job_queue.run_once(db.init_db, 0, job_kwargs={"misfire_grace_time": 10})
app.job_queue.run_repeating(refresh_all_clients, interval=3600, first=10)

app.run_polling()
