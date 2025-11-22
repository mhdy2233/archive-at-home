import asyncio
import random
from urllib.parse import urljoin

from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from db.db import Client, User
from utils.http_client import http


async def fetch_status(url: str) -> tuple[dict | None, bool | None]:
    """请求节点状态信息"""
    try:
        resp = await http.get(urljoin(url, "/status"), timeout=15)
        data = resp.json()
        return data["status"]["msg"], data["status"]["enable_GP_cost"]
    except Exception as e:
        logger.error(f"获取节点 {url} 状态失败：{e}")
        return None, None


async def refresh_client_status(client: Client, app=None) -> None:
    """刷新单个节点状态"""
    status_data, enable_GP_cost = await fetch_status(client.url)
    remind = False
    if status_data is None:
        client.status = "网络异常"
        remind = True
    else:
        try:
            # 更新节点基础信息
            client.enable_GP_cost = enable_GP_cost
            client.EX = status_data.get("EX")
            client.Free = status_data.get("Free")
            client.GP = status_data.get("GP")
            client.Credits = status_data.get("Credits")

            # 判定节点状态
            client.status = "正常"
            if client.EX != "EX":
                client.status = "无法访问ex站点! "
            elif not client.Free and not client.enable_GP_cost:
                client.status = "配额不足! "
            elif not (client.GP and client.Credits):
                client.status = "无法获取GP/C余额! "
                remind = True
            elif (
                not client.Free
                and int(client.GP) < 50000
                and int(client.Credits) < 10000
            ):
                client.status = "GP/C不足! "

        except Exception as e:
            logger.error(f"刷新节点 {client.url} 状态时发生错误: {e}")
            client.status = "状态信息获取失败，请检查节点！"
            remind = True

    if remind and app:
        text = f"节点异常\nURL：{client.url}\n状态：{status_data}"
        keyboard = [
            [InlineKeyboardButton("管理节点", callback_data=f"client|{client.id}")]
        ]
        await app.bot.send_message(
            client.provider_id,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    await client.save()


async def refresh_all_clients(app=None):
    """刷新所有节点状态"""
    clients = await Client.all()
    tasks = [refresh_client_status(c, app) for c in clients if c.status != "停用"]
    await asyncio.gather(*tasks)


async def add_client(user_id: int, url: str) -> tuple[bool, str, bool | None]:
    """添加新节点"""
    status_data, enable_GP_cost = await fetch_status(url)
    if status_data is None:
        return False, "获取节点状态失败", None

    await Client.create(
        provider=await User.get(id=user_id),
        url=url,
        status="正常",
        enable_GP_cost=enable_GP_cost,
        EX=status_data.get("EX"),
        Free=status_data.get("Free"),
        GP=status_data.get("GP"),
        Credits=status_data.get("Credits"),
    )
    return True, "正常", enable_GP_cost


async def get_available_clients(require_GP: int, timeout: int) -> list[Client]:
    """获取可用节点"""
    clients = []
    c = await Client.all()
    for x in c:
        if x.enable_GP_cost == 0 and str(x.Free) == "0":
            continue
        if timeout == 1 and x.enable_GP_cost == 0:
            continue
        if x.status == "正常":
            if x.GP != "None":
                if int(x.GP) >= int(require_GP):
                    clients.append(x)

    random.shuffle(clients)
    return clients
