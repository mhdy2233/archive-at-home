from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from db.db import User
from utils.ehArchiveD import GUrl
from utils.GP_action import checkin, deduct_GP, get_current_GP
from utils.resolve import ehentai, get_download_url

app = FastAPI()


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


@app.post("/resolve")
async def resolve(request: Request):
    try:
        data = await request.json()
        apikey = data.get("apikey")
        gid = data.get("gid")
        token = data.get("token")

        if not all([apikey, gid, token]):
            return format_response(1, "参数不完整")

        user = await verify_user(apikey)
        if isinstance(user, JSONResponse):
            return user

        try:
            gallery_info = await ehentai.get_archiver_info(GUrl(gid, token))
            require_GP = await ehentai.get_required_gp(gallery_info)
            user_GP_cost = int(gallery_info.filesize / 52428.8)
        except Exception:
            return format_response(4, "获取画廊信息失败")

        current_GP = get_current_GP(user)
        if current_GP < user_GP_cost:
            return format_response(5, "GP 不足")

        d_url, _ = await get_download_url(user, gid, token, require_GP > 0)
        if not d_url:
            return format_response(6, "解析失败")

        await deduct_GP(user, user_GP_cost)
        return format_response(0, "解析成功", {"archive_url": d_url})

    except Exception as e:
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
