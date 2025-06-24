import re

import httpx

from config.config import config

http = httpx.AsyncClient(proxy=config["proxy"])

EX_BASE_URL = "https://exhentai.org"
EH_BASE_URL = "https://e-hentai.org"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    "Cookie": config["ehentai"]["cookies"],
}


def _get_base_url():
    try:
        res = httpx.get(EX_BASE_URL, headers=headers, proxy=config["proxy"])
        if res.text != "":
            return EX_BASE_URL
    except:
        pass
    return EH_BASE_URL


base_url = _get_base_url()


async def _archiver(gid, token, data=None):
    url = f"{base_url}/archiver.php?gid={gid}&token={token}"
    response = await http.post(url, headers=headers, data=data)
    return response.text


async def get_GP_cost(gid, token):
    response = await _archiver(gid, token)
    original_div = re.search(r"float:left.*float:right", response, re.DOTALL).group()
    cost_text = re.search(r"<strong>(.*?)</strong>", original_div).group(1)
    client_GP_cost = (
        0 if cost_text == "Free!" else int("".join(filter(str.isdigit, cost_text)))
    )
    return client_GP_cost


async def get_download_url(gid, token):
    response = await _archiver(
        gid,
        token,
        {
            "dltype": "org",
            "dlcheck": "Download+Original+Archive",
        },
    )
    d_url = re.search(r'document\.location = "(.*?)";', response, re.DOTALL).group(1)
    if not d_url:
        raise RuntimeError("归档链接获取失败")
    await _archiver(gid, token, {"invalidate_sessions": "1"})
    return f"{d_url.removesuffix('?autostart=1')}?start=1"
