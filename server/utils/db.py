import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger
from tortoise import Tortoise, fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    apikey = fields.CharField(max_length=50, default=str(uuid.uuid4()))
    group = fields.CharField(max_length=50, default="普通用户")

    GP_records = fields.ReverseRelation["GPRecord"]
    clients = fields.ReverseRelation["Client"]
    archive_histories = fields.ReverseRelation["ArchiveHistory"]


class GPRecord(Model):
    user = fields.ForeignKeyField("models.User", related_name="GP_records")
    amount = fields.IntField()
    expire_time = fields.DatetimeField(
        default=lambda: datetime.now() + timedelta(days=7)
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
    client = fields.ForeignKeyField("models.Client", related_name="archive_histories")
    time = fields.DatetimeField(default=datetime.now)


# 获取用户当前有效 GP 总额
async def get_current_GP(user: User) -> int:
    now = datetime.now(tz=timezone.utc)
    return sum(
        r.amount for r in user.GP_records if r.expire_time > now and r.amount > 0
    )


async def checkin(user: User):
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()

    already_checked = any(
        record.source == "签到"
        and record.expire_time.astimezone(ZoneInfo("Asia/Shanghai")).date()
        == today + timedelta(days=7)
        for record in user.GP_records
    )

    if already_checked:
        return 0, 0

    original_balance = await get_current_GP(user)
    amount = random.randint(10000, 20000)
    await GPRecord.create(user=user, amount=amount)
    logger.info(f"{user.name}（{user.id}）签到成功，获得 {amount} GP")

    return amount, original_balance + amount


# 扣除 GP
async def deduct_GP(user: User, amount: int):
    now = datetime.now()
    valid_GP = (
        await user.GP_records.filter(expire_time__gt=now, amount__gt=0)
        .order_by("expire_time")
        .all()
    )

    total_deducted = 0
    for record in valid_GP:
        if total_deducted >= amount:
            break
        deduct_amount = min(record.amount, amount - total_deducted)
        record.amount -= deduct_amount
        total_deducted += deduct_amount
        await record.save()


# 初始化数据库
async def init_db(_):
    BASE_DIR = Path(__file__).parent.parent
    db_path = BASE_DIR / "db" / "bot_data.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    await Tortoise.init(db_url=f"sqlite://{db_path}", modules={"models": [__name__]})
    await Tortoise.generate_schemas()
