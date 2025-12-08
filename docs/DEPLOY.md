# Archive@Home 部署指南

## 目录
- [快速开始](#快速开始)
- [部署模式](#部署模式)
- [服务端部署](#服务端部署)
  - [Docker Compose (推荐)](#docker-compose-推荐)
  - [手动部署](#手动部署)
- [TelePress 配置 (重要)](#telepress-配置)
- [节点部署](#节点部署)
- [配置详解](#配置详解)

---

## 快速开始

### 前置要求

| 要求 | 说明 | 获取方式 |
|------|------|----------|
| **Telegram Bot Token** | 必填 | [@BotFather](https://t.me/BotFather) 发送 `/newbot` |
| **E-Hentai Cookie** | 必填 | 浏览器 F12 → Network → Cookie (需里站权限) |
| **R2 / S3 配置** | R2 模式必填 | Cloudflare Dashboard 或其他 S3 服务商 |
| **TelePress 配置** | Telegraph 模式必填 | 详见下文 [TelePress 配置](#telepress-配置) |

---

## 部署模式

本项目支持两种存储模式，请根据需求选择：

| 模式 | 配置文件设置 | 特点 | 适用场景 |
|------|------------|------|----------|
| **R2 模式** | `storage_mode: r2` | 图片存储在 R2/S3，直接返回文件下载链接，不生成文章。需配置 Rclone。 | 追求稳定、建立私有归档库的用户 |
| **Telegraph 模式** | `storage_mode: telegraph` | 利用 TelePress 发布图文并茂的 Telegraph 文章。需配置外部图床（支持 R2/Imgur 等）。 | 轻量级部署、在线阅读体验优先的用户 |

> **提示**: 你可以在 Telegraph 模式下使用 R2 作为图床（推荐），这样既能享受 Telegraph 的阅读体验，又能拥有 R2 的稳定存储。

---

## 服务端部署

### Docker Compose (推荐)

1. **克隆仓库**
   ```bash
   git clone https://github.com/zoidberg-xgd/archive-at-home.git
   cd archive-at-home
   ```

2. **创建配置文件**
   ```bash
   cp server/config/config.yaml.example server/config/config.yaml
   ```
   编辑 `server/config/config.yaml`，填写 Bot Token、Cookie 等信息。

3. **配置存储 (二选一)**

   - **如果是 R2 模式**:
     需配置 Rclone。将你的 `rclone.conf` 复制到数据目录：
     ```bash
     mkdir -p data/rclone
     cp ~/.config/rclone/rclone.conf data/rclone/
     ```
     *(容器内路径为 `/root/.config/rclone/rclone.conf`，已在 docker-compose 中映射)*

   - **如果是 Telegraph 模式**:
     需配置 TelePress（见下文）。建议创建 `telepress.json` 并映射：
     ```bash
     # 创建配置文件
     touch data/telepress.json
     # 编辑内容 (见 TelePress 配置章节)
     ```
     需要在 `docker-compose.yml` 中添加映射（或使用环境变量）：
     ```yaml
     volumes:
       - ./data/telepress.json:/root/.telepress.json
     environment:
       - TZ=Asia/Shanghai
       # 可选：使用环境变量配置 TelePress
       # - TELEPRESS_IMAGE_HOST_TYPE=rclone
       # - TELEPRESS_IMAGE_HOST_REMOTE_PATH=r2:archive-gallery
       # - TELEPRESS_IMAGE_HOST_PUBLIC_URL=https://pub-xxx.r2.dev
     ```

4. **启动服务**
   ```bash
   docker-compose up -d
   ```

### 手动部署

1. **环境准备**
   - Python 3.10+
   - Rclone (建议安装，用于 R2 模式或 TelePress Rclone 模式)

2. **安装依赖**
   ```bash
   cd server
   pip install -r requirements.txt
   ```

3. **配置文件**
   ```bash
   cp config/config.yaml.example config/config.yaml
   # 编辑 config.yaml
   ```

4. **配置 TelePress (仅 Telegraph 模式)**
   在用户主目录创建 `~/.telepress.json` (见下文)。

5. **运行**
   ```bash
   python main.py
   ```

---

## TelePress 配置

> **注意**: 本项目使用 `telepress` 库发布 Telegraph 文章。由于 Telegraph 官方不再支持直接上传图片，你**必须**配置一个外部图床。

你通过 `~/.telepress.json` 文件或环境变量来配置它。

### 配置文件示例 (`~/.telepress.json`)

#### 1. 使用 Rclone (推荐 R2/S3 用户)
> 直接复用项目已配置好的 Rclone 后端。这是最简单且性能最好的方式，无需配置额外的图床 API。

```json
{
    "image_host": {
        "type": "rclone",
        "remote_path": "r2:archive-gallery",
        "public_url": "https://pub-xxx.r2.dev",
        "rclone_flags": ["--transfers=32", "--checkers=32"]
    }
}
```
*   `remote_path`: Rclone 的远程路径（与 `rclone listremotes` 显示的一致）。
*   `public_url`: 对应的公开访问 URL。

#### 2. 使用 Imgur (免费推荐)
```json
{
    "image_host": {
        "type": "imgur",
        "client_id": "你的_Imgur_Client_ID"
    }
}
```

#### 3. 使用 ImgBB
```json
{
    "image_host": {
        "type": "imgbb",
        "api_key": "你的_ImgBB_API_Key"
    }
}
```

#### 4. 使用 R2 / S3 API (不推荐)
如果你无法使用 Rclone，可以使用原生 API 模式。
```json
{
    "image_host": {
        "type": "r2",
        "account_id": "你的_Cloudflare_Account_ID",
        "access_key_id": "你的_R2_Access_Key",
        "secret_access_key": "你的_R2_Secret_Key",
        "bucket": "存储桶名称",
        "public_url": "https://pub-xxx.r2.dev"
    }
}
```

#### 5. 使用自定义图床
```json
{
    "image_host": {
        "type": "custom",
        "upload_url": "https://your-site.com/api/1/upload",
        "method": "POST",
        "file_field": "image",
        "headers": {"X-API-Key": "your_key"},
        "response_url_path": "image.url"
    }
}
```

### 调整上传限制 (可选)
如果你使用的图床支持更大的文件（例如 Imgur 支持 20MB），你可以在配置中放宽限制：

```json
{
    "image_host": {
        "type": "imgur",
        "client_id": "...",
        "max_size_mb": 20
    }
}
```
*默认限制为 5MB (Telegraph 标准)*。

---

## 节点部署

节点用于分布式解析 E-Hentai 画廊。你可以部署在 Cloudflare Workers 上，也可以使用 Docker 部署本地节点。

### 方式一：Docker Compose (最简单)
如果你的服务器性能足够，可以直接和 Server 一起部署。

1. **创建 Client 配置文件**
   ```bash
   cp client/config/config.yaml.example client/config/config.yaml
   ```
   编辑 `client/config/config.yaml`，填入 E-Hentai Cookie。

2. **修改 `docker-compose.yml` (可选)**
   默认的 `docker-compose.yml` 已经包含了 `client` 服务。如果你不需要本地节点，可以注释掉 `client` 部分。

3. **启动服务**
   ```bash
   docker-compose up -d
   ```

4. **在 Bot 中添加节点**
   - 发送 `/clientmgr`
   - 点击 **"➕ 添加节点"**
   - 输入 URL：`http://archive-at-home-client:4655`
   - *(注意：这是 Docker 内部网络地址，无需修改)*

### 方式二：Cloudflare Workers (推荐用于分流)
如果你希望降低服务器负载，或利用 Cloudflare 的网络优势。

1. 登录 Cloudflare Dashboard，进入 **Workers & Pages**。
2. 创建一个新 Worker。
3. 复制项目根目录下的 `client_worker.js` 内容到 Worker 编辑器。
4. 修改代码顶部的 `COOKIE` 变量为你的 E-Hentai Cookie。
5. 保存并部署。
6. 复制 Worker 的 URL (例如 `https://my-worker.user.workers.dev`)，稍后可用于测试或负载均衡。

### 在 Bot 中添加节点

1. 向 Bot 发送 `/clientmgr` 命令（管理员或节点提供者权限）。
2. 点击 **"➕ 添加节点"**。
3. 发送 Worker 的 URL（例如 `https://my-worker.user.workers.dev`）。
4. 添加成功后，Bot 即可调度该节点进行解析下载。

*(注：服务端会自动分配任务给节点，目前版本服务端主要负责调度和下载，Worker 节点主要辅助解析)*

---

## 配置详解

### `config.yaml` 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `BOT_TOKEN` | Telegram Bot 凭证 | `123456:ABC-def...` |
| `admin` | 管理员 ID 列表 (数字) | `[123456789]` |
| `eh_cookie` | E-Hentai Cookie 字符串 | `ipb_member_id=...; igneous=...` |
| `storage_mode` | 存储模式 | `r2` 或 `telegraph` |
| `preview_url` | **(R2模式)** 图片访问前缀 | `https://pub-xxx.r2.dev/` (必须以/结尾) |
| `rclone_upload_remote` | **(R2模式)** Rclone 远程名称 | `r2:bucket-name` |
| `download_folder` | 下载临时目录 | `/download` (Docker内路径) |

### 常见问题

**Q: 为什么上传失败显示 "File too large"?**
A: 默认限制是 5MB。如果你的图床支持更大图片（如 Imgur 支持 20MB），请在 `~/.telepress.json` 中添加 `"max_size_mb": 20`。

**Q: R2 模式下图片无法加载？**
A: 请检查 `preview_url` 是否配置正确，并且 R2 存储桶已开启公开访问 (Public Access) 或绑定了域名。

**Q: Telegraph 模式需要 Rclone 吗？**
A: 如果你选择 **Rclone 模式** 作为 TelePress 图床，则需要 Rclone。如果你使用 Imgur/ImgBB 等 HTTP 图床，则不需要。
