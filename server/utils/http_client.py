import httpx

from config.config import cfg

# 创建一个全局的 AsyncClient 实例
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
}

cookie_str = cfg['eh_cookie']  # ipb_member_id=7405455; sk=abcdef
cookie_jar = httpx.Cookies()
for item in cookie_str.split(";"):
    if "=" in item:
        k, v = item.strip().split("=", 1)
        cookie_jar.set(k, v, domain=".exhentai.org")

http = httpx.AsyncClient(proxy=cfg["proxy"], headers=headers, cookies=cookie_jar, timeout=10, follow_redirects=True)
