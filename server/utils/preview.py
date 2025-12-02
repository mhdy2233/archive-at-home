import re, httpx
import aiohttp
import asyncio
import os
import zipfile
import subprocess
import shutil

from telegraph import Telegraph
from bs4 import BeautifulSoup
from loguru import logger

from config.config import cfg
from utils.http_client import http
from db.db import Preview

task_list = []

async def download_part(session, url, start, end, part_file):
    headers = {"Range": f"bytes={start}-{end}"}
    async with session.get(url, headers=headers) as resp:
        with open(part_file, "wb") as f:
            async for chunk in resp.content.iter_chunked(1024 * 1024):
                f.write(chunk)

async def async_multithread_download(url, filename, parts=8):
    try:
        async with aiohttp.ClientSession() as session:
            # 获取文件大小
            async with session.head(url) as resp:
                size = int(resp.headers.get("Content-Length", 0))

            block = size // parts
            tasks = []

            for i in range(parts):
                start = i * block
                end = size - 1 if i == parts - 1 else (i + 1) * block - 1

                part_file = f"{cfg['download_folder']}/{filename}.part{i}"
                task = download_part(session, url, start, end, part_file)
                tasks.append(task)

            await asyncio.gather(*tasks)

        # 合并文件
        with open(f"{cfg['download_folder']}/{filename}", "wb") as out:
            for i in range(parts):
                with open(f"{cfg['download_folder']}/{filename}.part{i}", "rb") as f:
                    out.write(f.read())
                os.remove(f"{cfg['download_folder']}/{filename}.part{i}")
    except Exception as e:
        return False, e
    else:
        return True

async def telegraph_upload(title, urls, gid):
    # 1. 创建 telegraph 对象
    telegraph = Telegraph(access_token=cfg['ph_token'])

    # 2. 创建匿名账号（只需一次）
    # telegraph.create_account(short_name=USERNAME, author_name=USERNAME, author_url="https://t.me/lajijichang")
        # 3. 生成内容结构
    content = []

    # 3.3 插入图集
    content.extend([{"tag": "img", "attrs": {"src": f"{cfg['preview_url']}{gid}/{u}"}} for u in urls])

    # 3.4 插入广告
    if cfg['AD']:
        content.append({"tag": "a", "attrs": {"href": cfg['AD']['url']}, "children": [cfg['AD']['text']]})

    # 4. 创建 Telegraph 页面
    page = telegraph.create_page(title=title, content=content, author_name=cfg['author_name'], author_url=cfg['author_url'])
    return 'https://telegra.ph/' + page['path']

async def monitor_folder(path, stop_event, mes, interval=5):
    """
    异步监控文件夹内文件数量变化，可随时终止。
    :param path: 文件夹路径
    :param stop_event: asyncio.Event 用于停止监控
    :param interval: 检查间隔秒数
    """
    old_count = -1

    print(f"开始监控：{path}")

    while not stop_event.is_set():
        # 获取文件数量
        try:
            count = sum(1 for _ in os.scandir(path))
        except FileNotFoundError:
            print(f"目录不存在：{path}")
            break

        # 检测变化
        if count != old_count:
            old_count = count
        await mes.edit_text(f"剩余上传进度：{count}")
        await asyncio.sleep(interval)

async def get_gallery_images(gid, token, d_url, mes, user):
    res = await http.get(f"https://exhentai.org/g/{gid}/{token}?inline_set=tr_40", follow_redirects=True)
    if res.status_code == 200:
        if res.text == "Key missing, or incorrect key provided.":
            return(False, "请检查画廊是否正确")
        else:
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.find('h1', id='gn').text
            await mes.edit_text("开始下载...")
            os.makedirs(f"{cfg['download_folder']}", exist_ok=True)
            dow = await async_multithread_download(d_url + "1?start=1", f"{gid}.zip", parts=cfg['preview_download_thread'])
            if dow == True:
                await mes.edit_text("下载完成，开始解压...")
                try:
                    os.makedirs(f"{cfg['temp_folder']}/{gid}", exist_ok=True)
                    with zipfile.ZipFile(f"{cfg['download_folder']}/{gid}.zip", "r") as zip_ref:
                        zip_ref.extractall(f"{cfg['temp_folder']}/{gid}")
                except Exception as e:
                    return False, e
                else:
                    # 自然顺序排序函数
                    def natural_sort_key(s):
                        # 分割字符串和数字，数字部分转换为整数
                        return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

                    def natural_sort_key(s):
                        """自然排序的 key 函数，将字符串中的数字单独提取出来排序"""
                        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

                    # 获取所有文件名（不包含子目录）
                    image_names = [f for f in os.listdir(f"{cfg['temp_folder']}/{gid}") if os.path.isfile(os.path.join(f"{cfg['temp_folder']}/{gid}", f))]

                    # 自然排序
                    image_names.sort(key=natural_sort_key)
                    print(image_names)
                    await mes.edit_text("解压完成，开始上传...")
                    stop_event = asyncio.Event()
                    task = asyncio.create_task(monitor_folder(f"{cfg['temp_folder']}/{gid}", stop_event, mes))
                    try:
                        result = subprocess.run(
                        ['rclone', 'move', f"{cfg['temp_folder']}/{gid}/", f"{cfg['rclone_upload_remote']}/{gid}", '-P', '--transfers=8'],
                        stdout=subprocess.PIPE,  # 捕获标准输出
                        stderr=subprocess.PIPE,  # 捕获错误输出
                        text=True,               # 输出作为字符串
                        check=True               # 检查命令是否成功
                        )
                        logger.info(f"标准输出{result.stdout}")
                        # 将新链接添加到数据中
                        logger.info(f"标准输出{result.stderr}")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"程序发生错误{e.stderr}")
                        return False, e
                    else:
                        stop_event.set()
                        ph_url = await telegraph_upload(title=title, urls=image_names, gid=gid)
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
    else:
        print("400")

async def preview_start():
    while True:
        if task_list:
            x = task_list.pop(0)
            task = await get_gallery_images(gid=x['gid'], token=x['token'], mes=x['mes'], d_url=x['d_url'], user=x['user'])
            if task:
                continue
            else:
                x['mes'].edit_text(f'错误: \n{task[1]}')
            for x in task_list:
                x['mes'].edit_text(f"获取下载链接成功，已加入队列({len(task_list)})...")
        await asyncio.sleep(1)