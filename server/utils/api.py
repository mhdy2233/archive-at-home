from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from utils.db import User, deduct_GP, get_current_GP
from utils.ehArchiveD import GUrl
from utils.resolve import ehentai, get_download_url

app = FastAPI()


@app.post("/")
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

        user = await User.get_or_none(apikey=apikey).prefetch_related("GP_records")
        if not user:
            return JSONResponse(
                content={"retcode": 2, "msg": "无效的 API Key"}, status_code=403
            )

        if user.group == "黑名单":
            return JSONResponse(
                content={"retcode": 3, "msg": "您已被封禁"}, status_code=403
            )

        # 获取画廊信息和所需 GP
        try:
            gallery_info = await ehentai.get_archiver_info(GUrl(gid, token))
            require_GP = await ehentai.get_required_gp(gallery_info)
            user_GP_cost = int(gallery_info.filesize / 52428.8)
        except Exception:
            return JSONResponse(
                content={"retcode": 4, "msg": "获取画廊信息失败"}, status_code=200
            )

        # 检查 GP 是否足够
        current_GP = await get_current_GP(user)
        if current_GP < user_GP_cost:
            return JSONResponse(
                content={"retcode": 5, "msg": "GP 不足"}, status_code=200
            )

        # 获取下载链接
        d_url, _ = await get_download_url(user, gid, token, require_GP > 0)
        if not d_url:
            return JSONResponse(
                content={"retcode": 6, "msg": "解析失败"}, status_code=200
            )

        # 扣除 GP 并返回成功结果
        await deduct_GP(user, user_GP_cost)
        return JSONResponse(
            content={"retcode": 0, "msg": "解析成功", "archive_url": d_url},
            status_code=200,
        )

    except Exception as e:
        return JSONResponse(
            content={"retcode": 99, "msg": f"服务器内部错误: {str(e)}"},
            status_code=500,
        )
