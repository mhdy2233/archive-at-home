import re
import aiohttp
import asyncio
import os
import shutil
import zipfile
import subprocess
import aiofiles

import telepress
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

def natural_sort_key(s):
    """自然排序的 key 函数，将字符串中的数字单独提取出来排序"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

async def get_gallery_images(gid, token, mes, user):
    res = await http.get(f"https://exhentai.org/g/{gid}/{token}?inline_set=tr_40", follow_redirects=True)
    if res.status_code == 200:
        if res.text == "Key missing, or incorrect key provided.":
            return(False, "请检查画廊是否正确")
        else:
            soup = BeautifulSoup(res.text, 'html.parser')
            title_node = soup.find('h1', id='gn')
            title = title_node.text if title_node else "Unknown Title"
            
            # Fetch download url logic
            try:
                _, _, thumb, require_GP, timeout = await get_gallery_info(
                    gid, token
                )
            except Exception as e:
                await mes.edit_text("❌ 画廊解析失败，请检查链接或稍后再试")
                logger.error(f"画廊 https://exhentai.org/g/{gid}/{token} 解析失败：{e}")
                return False, e

            d_url = await get_download_url(
                user, gid, token, "res", int(require_GP['res']), timeout
            )
            
            if not d_url:
                await mes.edit_text("❌ 获取下载链接失败")
                return False, "获取下载链接失败"

            await deduct_GP(user, int(require_GP['res']))
            
            await mes.edit_text("开始下载...")
            os.makedirs(f"{cfg['download_folder']}", exist_ok=True)
            
            dow = await async_multithread_download(d_url + "1?start=1", f"{gid}.zip", parts=cfg['preview_download_thread'])
            if dow[0] == True:
                try:
                    # 获取存储模式: "r2" 或 "telegraph"
                    storage_mode = cfg.get('storage_mode', 'r2')
                    
                    if storage_mode == 'telegraph':
                        # Telegraph 直传模式：直接用 zip 文件上传
                        await mes.edit_text("下载完成，开始上传到 Telegraph...")
                        
                        ph_url = await asyncio.to_thread(
                            telepress.publish,
                            f"{cfg['download_folder']}/{gid}.zip",
                            title=title
                        )
                    else:
                        # R2 模式：解压后上传到 R2
                        await mes.edit_text("下载完成，开始解压...")
                        
                        os.makedirs(f"{cfg['temp_folder']}/{gid}", exist_ok=True)
                        with zipfile.ZipFile(f"{cfg['download_folder']}/{gid}.zip", "r") as zip_ref:
                            zip_ref.extractall(f"{cfg['temp_folder']}/{gid}")
                        
                        image_names = [f for f in os.listdir(f"{cfg['temp_folder']}/{gid}") 
                                     if os.path.isfile(os.path.join(f"{cfg['temp_folder']}/{gid}", f))]
                        image_names.sort(key=natural_sort_key)
                        
                        await mes.edit_text("解压完成，开始上传(Rclone)...")
                        
                        result = subprocess.run(
                            ['rclone', 'move', f"{cfg['temp_folder']}/{gid}/", f"{cfg['rclone_upload_remote']}/{gid}", '-P', '--transfers=8'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=True
                        )
                        
                        image_urls = [f"{cfg['preview_url']}{gid}/{name}" for name in image_names]
                        
                        await mes.edit_text("上传完成，开始生成预览页(TelePress)...")
                        
                        publisher = telepress.TelegraphPublisher(token=cfg.get('ph_token'))
                        ph_url = await asyncio.to_thread(
                            publisher.publish_optimized_gallery,
                            image_urls,
                            title=title
                        )
                    
                    if ph_url:
                        await mes.edit_text(f"生成完成预览链接为:\n{ph_url}")
                        await Preview.create(
                            user=user,
                            gid=gid,
                            token=token,
                            ph_url=ph_url
                        )
                        return True
                    else:
                        await mes.edit_text("生成预览失败")
                        return False, "生成预览失败"
                        
                except Exception as e:
                    logger.error(f"Error: {e}")
                    return False, e
                finally:
                    # 清理文件
                    if os.path.exists(f"{cfg['download_folder']}/{gid}.zip"):
                        os.remove(f"{cfg['download_folder']}/{gid}.zip")
                    if os.path.exists(f"{cfg['temp_folder']}/{gid}"):
                        shutil.rmtree(f"{cfg['temp_folder']}/{gid}")
            else:
                print(dow[1])
                return False, dow[1]
    else:
        print("400")
        return False, "无法获取画廊信息"

async def preview_start():
    while True:
        if task_list:
            x = task_list.pop(0)
            task = await get_gallery_images(gid=x['gid'], token=x['token'], mes=x['mes'], user=x['user'])
            if task:
                continue
            else:
                try:
                    if isinstance(task, tuple) and len(task) > 1:
                        await x['mes'].edit_text(f'错误: \n{task[1]}')
                    else:
                        await x['mes'].edit_text(f'错误: 未知错误')
                except:
                    pass
            for i, task_item in enumerate(task_list):
                 try:
                    await task_item['mes'].edit_text(f"获取下载链接成功，已加入队列({i+1})...")
                 except:
                    pass
        await asyncio.sleep(1)
