import re

import httpx
from loguru import logger

from config.config import config

res = httpx.get("https://e-hentai.org/", proxy=config["proxy"])
test_url = re.search(r"https://e-hentai\.org/g/[0-9]+/[0-9a-z]+", res.text).group()


async def get_status(ehentai):
    try:
        archiver_info = await ehentai.get_archiver_info(test_url)
        require_GP = await ehentai.get_required_gp(archiver_info)
        result = "无免费额度" if require_GP else "正常"
    except Exception as e:
        logger.error(e)
        result = "解析功能异常"

    return {"msg": result, "enable_GP_cost": config["ehentai"]["enable_GP_cost"]}
