import asyncio
import time
from collections import defaultdict
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from db.db import User
from utils.ehentai import get_GP_cost
from utils.GP_action import checkin, deduct_GP, get_current_GP
from utils.resolve import get_download_url, get_gallery_info

processing_tasks = {}
results_cache = defaultdict(dict)
lock = asyncio.Lock()

app = FastAPI()


async def clean_results_cache(_):
    now = time.time()
    keys_to_delete = []

    for key, value in results_cache.items():
        if not value or value.get("expire_time", 0) < now:
            keys_to_delete.append(key)

    for key in keys_to_delete:
        results_cache.pop(key, None)


def format_response(code: int, msg: str, data: dict = None):
    if data is None:
        data = {}
    return JSONResponse(
        content={"code": code, "msg": msg, "data": data}, status_code=200
    )


def handle_exception(e: Exception, default_code=99):
    return format_response(default_code, f"服务器内部错误: {str(e)}")


async def verify_user(apikey: str):
    if not apikey:
        return format_response(1, "参数不完整")

    user = await User.get_or_none(apikey=apikey).prefetch_related("GP_records")
    if not user:
        return format_response(2, "无效的 API Key")

    if user.group == "黑名单":
        return format_response(3, "您已被封禁")

    return user


async def process_resolve(user, gid, token, image_quality):
    try:
        require_GP = await get_GP_cost(gid, token)
    except Exception:
        return 4, "获取画廊信息失败", None, None

    if (
        not isinstance(require_GP, dict)
        or "org" not in require_GP
        or "res" not in require_GP
    ):
        return 8, "画廊 GP 信息解析异常", None, None

    if image_quality not in ("org", "res"):
        return 9, "参数 image_quality 非法", None, None

    selected_cost = require_GP.get(image_quality) or 0

    # GP 余额校验
    if get_current_GP(user) < int(selected_cost):
        return 5, "GP 不足", None, selected_cost

    # 获取下载链接
    _, _, _, _, timeout = await get_gallery_info(gid, token)
    d_url = await get_download_url(user, gid, token, image_quality, int(selected_cost), timeout)
    if d_url:
        d_url = d_url + "0?start=1" if image_quality == "org" else d_url + "1?start=1"
        await deduct_GP(user, int(selected_cost))
        return 0, "解析成功", d_url, selected_cost
    return 6, "解析失败", None, selected_cost


@app.post("/resolve")
async def handle_resolve(request: Request):
    try:
        data = await request.json()
        apikey = data.get("apikey")
        gid = data.get("gid")
        token = data.get("token")
        image_quality = data.get("image_quality", "org")  # 可选参数
        force_resolve = data.get("force_resolve", False)
        if not all([apikey, gid, token]):
            return format_response(1, "参数不完整")

        user = await verify_user(apikey)
        if isinstance(user, JSONResponse):
            return user

        # 缓存 key 包含清洗度，避免不同质量串用
        key = f"{user.id}|{gid}|{image_quality}"

        cache = results_cache.get(key)
        if cache and cache.get("expire_time", 0) > time.time() and not force_resolve:
            return format_response(
                0,
                "使用缓存记录",
                {"archive_url": cache["d_url"], "image_quality": image_quality},
            )

        task = processing_tasks.get(key)
        if not task:
            async with lock:
                task = processing_tasks.get(key)
                if not task:
                    task = asyncio.create_task(
                        process_resolve(user, gid, token, image_quality)
                    )
                    processing_tasks[key] = task

        try:
            code, msg, d_url, gp_cost = await task
            if not d_url:
                return format_response(
                    code, msg, {"image_quality": image_quality, "gp_cost": gp_cost}
                )

            results_cache[key] = {"d_url": d_url, "expire_time": time.time() + 86400}
            return format_response(
                code,
                msg,
                {
                    "archive_url": d_url,
                    "image_quality": image_quality,
                    "gp_cost": gp_cost,
                },
            )

        finally:
            async with lock:
                if processing_tasks.get(key) == task:
                    del processing_tasks[key]

    except Exception as e:
        traceback.print_exc()
        return handle_exception(e)


@app.post("/balance")
async def balance(request: Request):
    try:
        data = await request.json()
        apikey = data.get("apikey")
        user = await verify_user(apikey)
        if isinstance(user, JSONResponse):
            return user

        current_GP = get_current_GP(user)
        return format_response(0, "查询成功", {"current_GP": current_GP})

    except Exception as e:
        return handle_exception(e)


@app.post("/checkin")
async def checkin_request(request: Request):
    try:
        data = await request.json()
        apikey = data.get("apikey")
        user = await verify_user(apikey)
        if isinstance(user, JSONResponse):
            return user

        amount, current_GP = await checkin(user)
        if not amount:
            return format_response(7, "今日已签到")

        return format_response(
            0, "签到成功", {"get_GP": amount, "current_GP": current_GP}
        )

    except Exception as e:
        return handle_exception(e)


@app.get("/")
async def redirect():
    return RedirectResponse(url="https://t.me/EH_ArBot", status_code=301)
