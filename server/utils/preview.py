import re, math
import aiohttp
import asyncio
import os
import zipfile
import subprocess
import shutil
import aiofiles

from telegram.ext import ContextTypes

from telegraph import Telegraph
from bs4 import BeautifulSoup
from loguru import logger

from config.config import cfg
from utils.http_client import http
from db.db import Preview
from utils.GP_action import deduct_GP, get_current_GP
from utils.resolve import get_download_url, get_gallery_info

task_list = []

async def download_part(session, url, start, end, part_file):
    headers = {"Range": f"bytes={start}-{end}"}
    async with session.get(url, headers=headers) as resp:
        async with aiofiles.open(part_file, "wb") as f:
            async for chunk in resp.content.iter_chunked(1024*1024):
                await f.write(chunk)

async def merge_parts(filename, parts):
    out_file = f"{cfg['download_folder']}/{filename}"
    async with aiofiles.open(out_file, "wb") as out:
        for i in range(parts):
            part_file = f"{cfg['download_folder']}/{filename}.part{i}"
            async with aiofiles.open(part_file, "rb") as f:
                while True:
                    chunk = await f.read(1024*1024)
                    if not chunk:
                        break
                    await out.write(chunk)
            os.remove(part_file)
    return out_file

async def async_multithread_download(url, filename, parts=4):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as resp:
                size = int(resp.headers.get("Content-Length", 0))
            block = size // parts
            tasks = []
            for i in range(parts):
                start = i * block
                end = size - 1 if i == parts - 1 else (i + 1) * block - 1
                part_file = f"{cfg['download_folder']}/{filename}.part{i}"
                tasks.append(download_part(session, url, start, end, part_file))
            await asyncio.gather(*tasks)

        final_file = await merge_parts(filename, parts)
        return True, final_file

    except Exception as e:
        return False, e


async def telegraph_upload(title, urls, gid, thumb):
    telegraph = Telegraph(access_token=cfg['ph_token'])

    MAX_PER_PAGE = 200   # 每页最多 200 张图片
    total = len(urls)
    pages = math.ceil(total / MAX_PER_PAGE)

    page_links = []   # 存储分页后的链接

    for i in range(pages):
        start = i * MAX_PER_PAGE
        end = start + MAX_PER_PAGE
        part_urls = urls[start:end]

        # 内容结构
        content = []

        # 封面
        content.append({"tag": "img", "attrs": {"src": thumb}})

        # 图集
        content.extend([
            {"tag": "img", "attrs": {"src": f"{cfg['preview_url']}{gid}/{u}"}}
            for u in part_urls
        ])

        # 广告
        if cfg['AD']:
            content.append({
                "tag": "a",
                "attrs": {"href": cfg['AD']['url']},
                "children": [cfg['AD']['text']]
            })
            content.append("\n")

        # 子页标题，如：标题 (1/4)
        page_title = f"{title} ({i+1}/{pages})" if pages > 1 else title

        page = telegraph.create_page(
            title=page_title,
            content=content,
            author_name=cfg['author_name'],
            author_url=cfg['author_url']
        )

        page_links.append({"title": page_title, "content": content, "path": page['path']})
    if len(page_links) > 1:
        page_index_nodes = ["Pages / 分页: "]
        for index, x in enumerate(page_links):
            page_index_nodes.append(    
                {
                "tag": "p",
                "children": [
                    {"tag": "a", "attrs": {"href": f"/{x['path']}"}, "children": [f"[{index+1}]"]},
                    " "
                ]
            }
            )
        for index, x in enumerate(page_links):
            new_content = []
            if index > 0:
                new_content.append({
                    'tag': 'a',
                    'attrs': {'href': f"/{page_links[index - 1]['path']}"},
                    'children': ['◀ Previous / 上一页']
                })
                new_content.append(" | ")
            if index < (len(page_links) - 1):
                new_content.append({
                    'tag': 'a',
                    'attrs': {'href': f"/{page_links[index + 1]['path']}"},
                    'children': ['Next / 下一页 ▶']
                })
            new_content.append("\n")
            content = x['content']
            content+=new_content
            tmp = page_index_nodes
            tmp[index + 1]['tag'] = "strong"
            content+=tmp
            telegraph.edit_page(
                title=x['title'],
                path=x['path'],
                content=content
            )
    return f"https://telegra.ph/{page_links[0]['path']}"

async def get_gallery_images(gid, token, mes, user):
    res = await http.get(f"https://exhentai.org/g/{gid}/{token}?inline_set=tr_40", follow_redirects=True)
    if res.status_code == 200:
        if res.text == "Key missing, or incorrect key provided.":
            return(False, "请检查画廊是否正确")
        else:
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.find('h1', id='gn').text
            try:
                _, _, thumb, require_GP, timeout = await get_gallery_info(
                    gid, token
                )
            except Exception as e:
                await mes_edit_text(mes, "❌ 画廊解析失败，请检查链接或稍后再试")
                logger.error(f"画廊 https://exhentai.org/g/{gid}/{token} 解析失败：{e}")
                return
            d_url = await get_download_url(
                user, gid, token, "res", int(require_GP['res']), timeout
            )
            if d_url:
                await deduct_GP(user, int(require_GP['res']))
                await mes_edit_text(mes, "获取下载链接成功, 开始下载...")
                os.makedirs(f"{cfg['download_folder']}", exist_ok=True)
                dow = await async_multithread_download(d_url + "1?start=1", f"{gid}.zip", parts=cfg['preview_download_thread'])
                if dow[0] == True:
                    await mes_edit_text(mes, "下载完成，开始解压...")
                    try:
                        os.makedirs(f"{cfg['temp_folder']}/{gid}", exist_ok=True)
                        with zipfile.ZipFile(f"{cfg['download_folder']}/{gid}.zip", "r") as zip_ref:
                            zip_ref.extractall(f"{cfg['temp_folder']}/{gid}")
                    except Exception as e:
                        return False, e
                    else:
                        def natural_sort_key(s):
                            """自然排序的 key 函数，将字符串中的数字单独提取出来排序"""
                            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
                        
                        # 获取文件列表并自然排序
                        files = sorted(os.listdir(f"{cfg['temp_folder']}/{gid}"), key=natural_sort_key)

                        # 重命名
                        for idx, filename in enumerate(files, start=1):
                            old_path = os.path.join(f"{cfg['temp_folder']}/{gid}", filename)
                            if os.path.isfile(old_path):
                                ext = os.path.splitext(filename)[1]  # 获取扩展名
                                new_name = f"{idx:04d}{ext}"        # 生成 0001.jpg 格式
                                new_path = os.path.join(f"{cfg['temp_folder']}/{gid}", new_name)
                                os.rename(old_path, new_path)
                                print(f"{filename} -> {new_name}")

                        # 获取所有文件名（不包含子目录）
                        image_names = [f for f in os.listdir(f"{cfg['temp_folder']}/{gid}") if os.path.isfile(os.path.join(f"{cfg['temp_folder']}/{gid}", f))]

                        # 自然排序
                        image_names.sort(key=natural_sort_key)
                        print(image_names)
                        await mes_edit_text(mes, "解压完成，开始上传...")
                        try:
                            result = subprocess.run(
                            ['rclone', 'move', f"{cfg['temp_folder']}/{gid}/", f"{cfg['rclone_upload_remote']}/{gid}", '-P', f'--transfers={cfg['rclone_upload_thread']}'],
                            stdout=subprocess.PIPE,  # 捕获标准输出
                            stderr=subprocess.PIPE,  # 捕获错误输出
                            text=True,               # 输出作为字符串
                            check=True               # 检查命令是否成功
                            )
                            # logger.info(f"标准输出{result.stdout}")
                            # 将新链接添加到数据中
                            logger.info(f"标准输出{result.stderr}")
                        except subprocess.CalledProcessError as e:
                            logger.error(f"程序发生错误{e.stderr}")
                            return False, e
                        else:
                            # stop_event.set()
                            ph_url = await telegraph_upload(title=title, urls=image_names, gid=gid, thumb=thumb)
                            if ph_url:
                                await mes_edit_text(mes, f"生成完成, 预览链接为:\n{ph_url}")
                                await Preview.create(
                                    user=user,
                                    gid=gid,
                                    token=token,
                                    ph_url=ph_url
                                )
                            return True
                        finally:
                            shutil.rmtree(cfg['temp_folder'])
                            shutil.rmtree(cfg['download_folder'])
                else:
                    print(dow[1])
            elif d_url == None:
                await mes_edit_text(mes, "❌ 暂无可用服务器")
                logger.error(f"https://e-hentai.org/g/{gid}/{token}/ 下载链接获取失败")
            else:
                await mes_edit_text(mes, "❌ 获取下载链接失败")
                logger.error(f"https://e-hentai.org/g/{gid}/{token}/ 下载链接获取失败")
    else:
        print("400")

async def preview_start():
    while True:
        if task_list:
            x = task_list.pop(0)
            task = await get_gallery_images(gid=x['gid'], token=x['token'], mes=x['mes'], user=x['user'])
            if task:
                continue
            else:
                await mes_edit_text(x['mes'], f'错误: \n{task[1]}')
            for x in task_list:
                await mes_edit_text(x['mes'], f"获取下载链接成功，已加入队列({len(task_list)})...")
        await asyncio.sleep(1)

async def mes_edit_text(mes, text):
    context=ContextTypes.DEFAULT_TYPE
    if type(mes) == str:
        await context.bot.edit_message_text(
            text=text,
            inline_message_id=mes
        )
    else:
        await mes.edit_text(text)

async def preview_add(gid, token, require_GP, user):
    ph_url = await Preview.filter(gid=gid).first()
    result = {
        "status": None,
        "ph_url": None,
        "mes": None
    }
    if ph_url:
        result['status'] = True
        result['ph_url'] = ph_url.ph_url
        result['mes'] = f"已存在预览，本次不消耗GP\n{result['ph_url']}"
    else:
        current_GP = get_current_GP(user)
        if current_GP < int(require_GP):
            result['status'] = True
            result['mes'] = f"⚠️ GP 不足，当前余额：{current_GP}"
        else:
            for x in task_list:
                if x['gid'] == gid:
                    result['status'] = True
                    result['mes'] = f"已有相同任务, 请稍候重试"
                    
    return result