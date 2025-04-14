from datetime import datetime
from html import unescape
from io import BytesIO
from urllib.parse import urljoin

from loguru import logger

from config.config import cfg
from utils.client import get_available_clients
from utils.db import ArchiveHistory, Client
from utils.ehArchiveD import EHentai
from utils.http_client import http

ehentai = EHentai(cfg["eh_cookie"], cfg["proxy"])


async def get_gallery_info(url):
    """获取画廊基础信息 + 缩略图"""
    info = await ehentai.get_archiver_info(url)
    require_GP = await ehentai.get_required_gp(info)
    user_GP_cost = int(info.filesize / 52428.8)

    text = (
        f"📌 主标题：{unescape(info.title)}\n"
        f"📙 副标题：{unescape(info.title_jpn)}\n"
        f"📂 类型：{info.category}\n"
        f"👤 上传者：{info.uploader}\n"
        f"🕒 上传时间：{datetime.fromtimestamp(float(info.posted)):%Y-%m-%d %H:%M}\n"
        f"📄 页数：{info.filecount}\n"
        f"⭐ 评分：{info.rating}\n\n"
        f"💰 归档消耗 GP：{user_GP_cost}"
    )

    # 获取缩略图二进制流
    response = await http.get(info.thumb.replace("s.exhentai", "ehgt"))
    thumb = BytesIO(response.content)

    return (
        text,
        thumb,
        info.gid,
        info.token,
        user_GP_cost,
        require_GP > 0,
    )


async def get_download_url(user, gid, token, require_GP):
    """向可用节点请求下载链接"""
    clients = await get_available_clients(require_GP)

    for client in clients:
        try:
            response = await http.post(
                urljoin(client.url, "/resolve"),
                json={"username": user.name, "gid": gid, "token": token},
                timeout=60,
            )
            data = response.json()

            # 更新节点状态
            client.status = data["status"]["msg"]
            client.enable_GP_cost = data["status"]["enable_GP_cost"]
            await client.save()

            if data.get("msg") == "Success":
                await ArchiveHistory.create(
                    user=user,
                    gid=gid,
                    token=token,
                    GP_cost=data["require_GP"],
                    client=client,
                )
                logger.info(
                    f"节点 {client.url} 解析 https://e-hentai.org/g/{gid}/{token}/ 成功"
                )
                return data["d_url"], client
            error_msg = data.get("msg")
        except Exception as e:
            error_msg = e
        logger.error(
            f"节点 {client.url} 解析 https://e-hentai.org/g/{gid}/{token}/ 失败：{error_msg}"
        )

    return None, None


async def destroy_url(gid, token, client_id):
    """请求节点销毁链接"""
    client = await Client.get(id=client_id)
    try:
        await http.post(
            urljoin(client.url, "/destroy"),
            json={"gid": gid, "token": token},
            timeout=10,
        )
    except Exception:
        pass  # 容错处理，无需响应
