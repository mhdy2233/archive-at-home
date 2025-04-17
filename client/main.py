import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from config.config import config
from utils.ehArchiveD import EHentai, GUrl
from utils.status import GP_usage_log, get_status

logger.add("log.log", encoding="utf-8")

ehentai = EHentai(config["ehentai"]["cookies"], proxy=config["proxy"])

app = FastAPI()


@app.post("/resolve")
async def resolve(request: Request):
    try:
        data = await request.json()
        archiver_info = await ehentai.get_archiver_info(
            GUrl(data["gid"], data["token"])
        )
        require_GP = await ehentai.get_required_gp(archiver_info)
        if config["ehentai"]["max_GP_cost"] == 0 and require_GP > 0:
            msg = "Rejected"
            d_url = None
        else:
            d_url = await ehentai.get_download_url(archiver_info)
            msg = "Success"
            if config["ehentai"]["max_GP_cost"] > 0:
                GP_usage_log.append((time.time(), require_GP))
        logger.info(
            f"{data['username']} 归档 https://e-hentai.org/g/{data['gid']}/{data['token']}/  需要{require_GP}GP  {msg}"
        )
        return JSONResponse(
            content={
                "msg": msg,
                "d_url": d_url,
                "require_GP": require_GP,
                "status": await get_status(ehentai),
            }
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(content={"msg": "Failed", "status": "解析功能异常"})


@app.post("/destroy")
async def destroy(request: Request):
    try:
        data = await request.json()
        archiver_info = await ehentai.get_archiver_info(
            GUrl(data["gid"], data["token"])
        )
        if await ehentai.remove_download_url(archiver_info):
            logger.info(f"销毁 https://e-hentai.org/g/{data['gid']}/{data['token']}/")
            return JSONResponse(content={"msg": "Success"})
    except Exception as e:
        logger.error(e)
    return JSONResponse(content={"msg": "Failed"})


@app.get("/status")
async def status():
    return JSONResponse(content={"status": await get_status(ehentai)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=None, port=4655)
