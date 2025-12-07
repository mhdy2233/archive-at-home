# Archive@Home
一个基于 Telegram Bot 的分布式解析系统，用于解析 E-Hentai 画廊链接，并返回归档下载链接。

## 功能
- 分布式归档下载
- Telegraph 预览页生成 (支持 R2 / Imgur 等图床)
- 支持 Cloudflare R2 / Rclone 存储

## 快速开始

> 详细步骤请参考 [部署指南](docs/DEPLOY.md)

### 前置要求
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- E-Hentai Cookie (里站)
- Cloudflare 账号 (R2 存储) 或 其他图床配置 (Telegraph 模式)

### 部署服务端
```bash
# 克隆仓库
git clone https://github.com/zoidberg-xgd/archive-at-home.git
cd archive-at-home

# 配置
cp server/config/config.yaml.example server/config/config.yaml
# 编辑 server/config/config.yaml

# R2 模式需配置 Rclone
mkdir -p data/rclone
cp ~/.config/rclone/rclone.conf data/rclone/

# Telegraph 模式需配置 TelePress (可选)
# cp ~/.telepress.json data/telepress.json

# 启动
docker-compose up -d
```

### 部署节点
节点用于分布式解析，支持以下方式：

**方式一：Docker Compose (推荐)**
默认配置已包含 Client 节点。
1. `cp client/config/config.yaml.example client/config/config.yaml` 并填写配置
2. `docker-compose up -d`
3. 在 Bot 中添加 `http://archive-at-home-client:4655`

**方式二：Cloudflare Workers**
1. 复制 [client_worker.js](client_worker.js) 到 Workers 控制台
2. 修改 `COOKIE` 值
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
