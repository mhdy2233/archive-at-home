# Archive@Home
一个基于 Telegram Bot 的分布式解析系统，用于解析 E-Hentai 画廊链接，并返回归档下载链接。
## 部署节点

### Cloudflare Workers

1. 复制 [_worker.js](https://github.com/taskmgr818/archive-at-home/blob/main/server/_worker.js) 文件中的代码到你的 Workers 控制台代码编辑区  
2. 修改代码中的 `COOKIE` 值
3. 保存并部署

### Docker
1. 填写 [config.yaml](https://github.com/taskmgr818/archive-at-home/raw/main/client/config/config.yaml.example)
2. 执行
    ```text
    docker run --net host -v /yourconfigpath.yaml:/app/config/config.yaml --name archive-at-home-client taskmgr818/archive-at-home-client
    ```



## 鸣谢

**项目：**

- [mhdy2233/tg-eh-distributed-arc-bot](https://github.com/mhdy2233/tg-eh-distributed-arc-bot)
- [z-mio/ehentai_bot](https://github.com/z-mio/ehentai_bot)
- [Womsxd/ehArchiveD](https://github.com/Womsxd/ehArchiveD)

**开发者：**

- [@mhdy2233](https://github.com/mhdy2233)
- [@1235789gzy1](https://github.com/1235789gzy1)
- [@jiangtian616](https://github.com/jiangtian616)
