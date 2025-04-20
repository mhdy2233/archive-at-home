from collections import defaultdict
from datetime import datetime
from urllib.parse import urljoin

from loguru import logger

from config.config import cfg
from db.db import ArchiveHistory
from utils.client import get_available_clients
from utils.ehArchiveD import EHentai
from utils.http_client import http

ehentai = EHentai(cfg["eh_cookie"], cfg["proxy"])


async def fetch_tag_map(_):
    global tag_map
    tag_map = defaultdict(lambda: {"name": "", "data": {}})

    db = (
        await http.get(
            "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json",
            follow_redirects=True,
        )
    ).json()

    for entry in db["data"][2:]:
        namespace = entry["namespace"]
        tag_map[namespace]["name"] = entry["frontMatters"]["name"]
        tag_map[namespace]["data"].update(
            {key: value["name"] for key, value in entry["data"].items()}
        )


async def get_gallery_info(url):
    """获取画廊基础信息 + 缩略图"""
    info = await ehentai.get_archiver_info(url)
    require_GP = await ehentai.get_required_gp(info)
    user_GP_cost = int(info.filesize / 52428.8)

    raw_tags = info.tags
    tags = defaultdict(list)
    for item in raw_tags:
        ns, tag = item.split(":")
        tag_info = tag_map.get(ns, {})
        tag_name = tag_info["data"].get(tag)
        ns_name = tag_info["name"] or ns

        if tag_name:
            tags[ns_name].append(f"#{tag_name}")

    tag_text = "\n".join(
        f"{ns_name}：{' '.join(tags_list)}" for ns_name, tags_list in tags.items()
    )

    text = (
        f"📌 主标题：{info.title}\n"
        f"📙 副标题：{info.title_jpn}\n"
        f"📂 类型：{info.category}\n"
        f"👤 上传者：<a href='https://e-hentai.org/uploader/{info.uploader}'>{info.uploader}</a>\n"
        f"🕒 上传时间：{datetime.fromtimestamp(float(info.posted)):%Y-%m-%d %H:%M}\n"
        f"📄 页数：{info.filecount}\n"
        f"⭐ 评分：{info.rating}\n\n"
        f"<blockquote expandable>{tag_text}</blockquote>\n\n"
        f"💰 归档消耗 GP：{user_GP_cost}"
    )

    return (
        text,
        info.category != "Non-H",
        info.thumb.replace("s.exhentai", "ehgt"),
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
