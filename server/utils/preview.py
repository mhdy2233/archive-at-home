import re
import aiohttp
import asyncio
import os
import zipfile
import subprocess
import shutil
import aiofiles

from telegraph import Telegraph
from bs4 import BeautifulSoup
from loguru import logger

from config.config import cfg
from utils.http_client import http
from db.db import Preview
from utils.resolve import get_download_url, get_gallery_info
from utils.GP_action import deduct_GP

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
    # 1. 创建 telegraph 对象
    telegraph = Telegraph(access_token=cfg['ph_token'])

    # 2. 创建匿名账号（只需一次）
    # telegraph.create_account(short_name=USERNAME, author_name=USERNAME, author_url="https://t.me/lajijichang")
        # 3. 生成内容结构
    content = []

    # 3.1 插入封面
    content.append({"tag": "img", "attrs": {"src": thumb}})

    # 3.3 插入图集
    content.extend([{"tag": "img", "attrs": {"src": f"{cfg['preview_url']}{gid}/{u}"}} for u in urls])

    # 3.4 插入广告
    if cfg['AD']:
        content.append({"tag": "a", "attrs": {"href": cfg['AD']['url']}, "children": [cfg['AD']['text']]})

    # 4. 创建 Telegraph 页面
    page = telegraph.create_page(title=title, content=content, author_name=cfg['author_name'], author_url=cfg['author_url'])
    return 'https://telegra.ph/' + page['path']

# async def monitor_folder(path, stop_event, mes, interval=5):
#     """
#     异步监控文件夹内文件数量变化，可随时终止。
#     :param path: 文件夹路径
#     :param stop_event: asyncio.Event 用于停止监控
#     :param interval: 检查间隔秒数
#     """
#     print(f"开始监控：{path}")

#     while not stop_event.is_set():
#         # 获取文件数量
#         try:
#             count = sum(1 for f in os.listdir(path)if os.path.isfile(os.path.join(path, f)))
#         except FileNotFoundError:
#             print(f"目录不存在：{path}")
#             break

#         await mes.edit_text(f"剩余上传进度：{count}")
#         await asyncio.sleep(interval)

def telegraph_title_length(s):
    length = 0
    for ch in s:
        if ord(ch) < 128:  # ASCII 字符
            length += 1
        else:  # 中文 / emoji / 全角
            length += 2
    return length

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
                await mes.edit_text("❌ 画廊解析失败，请检查链接或稍后再试")
                logger.error(f"画廊 https://exhentai.org/g/{gid}/{token} 解析失败：{e}")
                return
            d_url = await get_download_url(
                user, gid, token, "res", int(require_GP['res']), timeout
            )
            if d_url:
                await deduct_GP(user, int(require_GP['res']))
                await mes.edit_text("获取下载链接成功, 开始下载...")
                os.makedirs(f"{cfg['download_folder']}", exist_ok=True)
                dow = await async_multithread_download(d_url + "1?start=1", f"{gid}.zip", parts=cfg['preview_download_thread'])
                if dow[0] == True:
                    await mes.edit_text("下载完成，开始解压...")
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
                        await mes.edit_text("解压完成，开始上传...")
                        # stop_event = asyncio.Event()
                        # task = asyncio.create_task(monitor_folder(f"{cfg['temp_folder']}/{gid}", stop_event, mes))
                        try:
                            result = subprocess.run(
                            ['rclone', 'move', f"{cfg['temp_folder']}/{gid}/", f"{cfg['rclone_upload_remote']}/{gid}", '-P', '--transfers=8'],
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
                                await mes.edit_text(f"生成完成预览链接为:\n{ph_url}")
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
                await mes.edit_text("❌ 暂无可用服务器")
                logger.error(f"https://e-hentai.org/g/{gid}/{token}/ 下载链接获取失败")
            else:
                await mes.edit_text("❌ 获取下载链接失败")
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
                x['mes'].edit_text(f'错误: \n{task[1]}')
            for x in task_list:
                x['mes'].edit_text(f"获取下载链接成功，已加入队列({len(task_list)})...")
        await asyncio.sleep(1)