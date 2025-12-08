import os, aiosqlite
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from tortoise import Tortoise, fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    apikey = fields.UUIDField(default=uuid4)
    group = fields.CharField(max_length=50, default="普通用户")

    GP_records = fields.ReverseRelation["GPRecord"]
    clients = fields.ReverseRelation["Client"]
    archive_histories = fields.ReverseRelation["ArchiveHistory"]
    previews = fields.ReverseRelation["Preview"]


class GPRecord(Model):
    user = fields.ForeignKeyField("models.User", related_name="GP_records")
    amount = fields.IntField()
    expire_time = fields.DatetimeField(
        default=lambda: datetime.now(tz=timezone.utc) + timedelta(days=7)
    )
    source = fields.CharField(max_length=50, default="签到")


class Client(Model):
    url = fields.CharField(max_length=255)
    status = fields.CharField(max_length=50)
    enable_GP_cost = fields.BooleanField()
    provider = fields.ForeignKeyField("models.User", related_name="clients")
    archive_histories = fields.ReverseRelation["ArchiveHistory"]


class ArchiveHistory(Model):
    user = fields.ForeignKeyField("models.User", related_name="archive_histories")
    gid = fields.CharField(max_length=20)
    token = fields.CharField(max_length=20)
    GP_cost = fields.IntField()
    client = fields.ForeignKeyField(
        "models.Client",
        related_name="archive_histories",
        null=True,
        on_delete=fields.SET_NULL,
    )
    time = fields.DatetimeField(default=lambda: datetime.now(tz=timezone.utc))

class Preview(Model):
    user = fields.ForeignKeyField("models.User", related_name="previeew")
    gid = fields.CharField(max_length=20)
    token = fields.CharField(max_length=20)
    ph_url = fields.CharField(max_length=255)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "bot_data.db"))

async def checkpoint_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA wal_checkpoint(FULL);")
        await db.commit()

# 初始化数据库
async def init_db():
    await Tortoise.init(db_url=f"sqlite://{DB_PATH}", modules={"models": [__name__]})
    await Tortoise.generate_schemas()
