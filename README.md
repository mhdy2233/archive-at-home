# Archive@Home
一个基于 Telegram Bot 的分布式解析系统，用于解析 E-Hentai 画廊链接，并返回归档下载链接。

当前部署bot为[**归档大王**](https://t.me/EH_AR_bot), bot通知频道 https://t.me/a_eh_arbot

欢迎加入我们！
可以选择贡献cookie，或者自行部署client，在bot通知频道留言加入。
**需要里站号欢迎访问 https://shop.mhdy.net?cid=2&mid=3**

## 功能Cloudflare Workers

1. 复制 [client_worker.js](https://github.com/taskmgr818/archive-at-home/blob/main/client_worker.js) 文件中的代码到你的 Workers 控制台代码编辑区  
2. 修改代码中的 `COOKIE` 值
3. 保存并部署
4. 在 Bot 中发送 `/clientmgr` 添加该节点 URL

## 文档
- [详细部署指南](docs/DEPLOY.md) - 包含 Cloudflare R2 和 TelePress 配置
- [API 文档](server/api_documentation.md)

## 鸣谢

**项目：**

- [mhdy2233/tg-eh-distributed-arc-bot](https://github.com/mhdy2233/tg-eh-distributed-arc-bot)
- [z-mio/ehentai_bot](https://github.com/z-mio/ehentai_bot)
- [Womsxd/ehArchiveD](https://github.com/Womsxd/ehArchiveD)

**开发者：**

- [@mhdy2233](https://github.com/mhdy2233)
- [@1235789gzy1](https://github.com/1235789gzy1)
- [@jiangtian616](https://github.com/jiangtian616)
