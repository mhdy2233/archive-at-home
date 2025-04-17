from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from utils.db import User, checkin, deduct_GP, get_current_GP
from utils.ehArchiveD import GUrl
from utils.resolve import ehentai, get_download_url

app = FastAPI()


async def verify_user(apikey: str):
    if not apikey:
        raise HTTPException(status_code=400, detail={"retcode": 1, "msg": "参数不完整"})

    user = await User.get_or_none(apikey=apikey).prefetch_related("GP_records")
    if not user:
        raise HTTPException(
            status_code=403, detail={"retcode": 2, "msg": "无效的 API Key"}
        )

    if user.group == "黑名单":
        raise HTTPException(status_code=403, detail={"retcode": 3, "msg": "您已被封禁"})

    return user


@app.post("/resolve")
async def resolve(request: Request):
    try:
        data = await request.json()
        apikey = data.get("apikey")
        gid = data.get("gid")
        token = data.get("token")

        if not all([apikey, gid, token]):
            return JSONResponse(
                content={"retcode": 1, "msg": "参数不完整"}, status_code=400
            )

        user = await verify_user(apikey)

        try:
            gallery_info = await ehentai.get_archiver_info(GUrl(gid, token))
            require_GP = await ehentai.get_required_gp(gallery_info)
            user_GP_cost = int(gallery_info.filesize / 52428.8)
        except Exception:
            return JSONResponse(
                content={"retcode": 4, "msg": "获取画廊信息失败"}, status_code=200
            )

        current_GP = await get_current_GP(user)
        if current_GP < user_GP_cost:
            return JSONResponse(
                content={"retcode": 5, "msg": "GP 不足"}, status_code=200
            )

        d_url, _ = await get_download_url(user, gid, token, require_GP > 0)
        if not d_url:
            return JSONResponse(
                content={"retcode": 6, "msg": "解析失败"}, status_code=200
            )

        await deduct_GP(user, user_GP_cost)
        return JSONResponse(
            content={"retcode": 0, "msg": "解析成功", "archive_url": d_url},
            status_code=200,
        )

    except HTTPException as he:
        return JSONResponse(content=he.detail, status_code=he.status_code)
    except Exception as e:
        return JSONResponse(
            content={"retcode": 99, "msg": f"服务器内部错误: {str(e)}"}, status_code=500
        )


@app.post("/balance")
async def balance(request: Request):
    try:
        data = await request.json()
        apikey = data.get("apikey")
        user = await verify_user(apikey)

        current_GP = await get_current_GP(user)
        return JSONResponse(
            content={"retcode": 0, "msg": "查询成功", "current_GP": current_GP},
            status_code=200,
        )

    except HTTPException as he:
        return JSONResponse(content=he.detail, status_code=he.status_code)
    except Exception as e:
        return JSONResponse(
            content={"retcode": 99, "msg": f"服务器内部错误: {str(e)}"}, status_code=500
        )


@app.post("/checkin")
async def checkin_request(request: Request):
    try:
        data = await request.json()
        apikey = data.get("apikey")
        user = await verify_user(apikey)

        amount, current_GP = await checkin(user)
        if not amount:
            return JSONResponse(
                content={"retcode": 7, "msg": "今日已签到"}, status_code=200
            )

        return JSONResponse(
            content={
                "retcode": 0,
                "msg": "签到成功",
                "get_GP": amount,
                "current_GP": current_GP,
            },
            status_code=200,
        )

    except HTTPException as he:
        return JSONResponse(content=he.detail, status_code=he.status_code)
    except Exception as e:
        return JSONResponse(
            content={"retcode": 99, "msg": f"服务器内部错误: {str(e)}"}, status_code=500
        )
