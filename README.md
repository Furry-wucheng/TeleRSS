# TeleRSS

AutoNotice 是一个自动化的通知服务，旨在通过 RSS 的方式监控信息源，并推送到 Telegram。

## ✨ 特性

- **多源支持**: 目前支持 RSS 订阅源监控。
- **消息推送**: 集成 Telegram Bot 推送通知，支持图片/视频/媒体组。
- **Bot 命令管理**: 通过 Telegram 命令动态管理关注列表，无需重启服务。
- **容器化**: 提供 Docker 支持，便于部署。
- **配置灵活**: 支持配置文件 (`config.ini`) 和环境变量双重配置。
- **任务调度**: 支持分批次任务执行，避免集中请求压力，并在服务重启后自动补跑错过的任务。

## 🤖 Bot 命令

服务启动时会自动向 Telegram 注册以下命令菜单，无需在 BotFather 手动配置：

| 命令                | 参数                              | 说明                            |
|:------------------|:--------------------------------|:------------------------------|
| `/add_id`         | `<user_id> [category] [source]` | 添加关注用户，category 默认为 `default` |
| `/remove_id`      | `<user_id>`                     | 删除关注用户                        |
| `/update_id_cate` | `<user_id> <category>`          | 更新用户分类，设为 `disable` 可暂停而不删除   |
| `/get_cate_list`  | 无                               | 获取所有分类列表                      |
| `/get_disable_id` | 无                               | 获取所有被暂停的关注用户                  |

> **提示**: 将用户分类设为 `disable` 即可暂停该用户的推送，而不必从数据库删除。

> 🔒 **权限控制**: 所有 Bot 命令均受 `admin_chat_id` 保护，只有配置的管理员 Chat ID 才能执行。其他用户发送命令会收到 `⛔ 权限不足` 提示。

## 🚀 快速开始

### 1. 准备工作

1. **准备配置文件**:

   ```bash
   cp config.example.ini config.ini
   # 编辑 config.ini 填入 RSS URL 和 Telegram Token
   ```

2. **部署或者找开放的 RSSHub**:
   本服务依赖 RSSHub 获取信息，推荐自行部署。以下是一个可供参考的 `docker-compose.yml` 配置：

   ```yaml
   services:
     rsshub:
       image: diygod/rsshub:latest
       restart: always
       ports:
         - 1200:1200
       environment:
         - CACHE_TYPE=memory
         - CACHE_EXPIRE=86400          # 缓存时间（秒），建议不要设太短避免频繁请求
         - TWITTER_AUTH_TOKEN=${X_TOKEN}   # X(Twitter) auth_token，从浏览器 Cookie 中获取
         - TWITTER_USERNAME=${X_USERNAME}  # X 账号用户名
         - TWITTER_PASSWORD=${X_PASSWORD}  # X 账号密码
         - PROXY_URI=http://172.17.0.1:7890  # 代理地址，172.17.0.1 为 Docker 宿主机默认网关
         - ANTISPAM_BLOCK_ATTACKER=true
       networks:
         - app-network

   networks:
     app-network:
       external: true
   ```

   > ⚠️ **安全提示**: 请勿将账号密码明文写入 `docker-compose.yml`，应使用 `.env` 文件管理敏感信息：
   >
   > ```bash
   > # .env 文件（不要提交到 Git！）
   > X_TOKEN=your_auth_token_here
   > X_USERNAME=your_username
   > X_PASSWORD=your_password
   > ```
   >
   > Docker Compose 会自动读取同目录下的 `.env` 文件，配置中的 `${X_TOKEN}` 等变量会自动替换。

   > **`PROXY_URI` 说明**: `172.17.0.1` 是 Docker bridge 网络中宿主机的默认 IP，RSSHub 容器通过此地址访问宿主机上运行的代理（如
   Clash）。如果你的宿主机代理监听在不同端口，请相应修改。

   部署教程可以去[我的主页](https://wucheng.work)查看（大概率还没写，但是欢迎访问！）。

3. **导入初始关注列表（可选）**:
   可以预先准备 `follower.txt`，通过 `import_script.py` 批量导入，也可以服务启动后直接用 Bot 命令添加。
   格式：每行一个 `user_id`，可选加空格和分类名。

   ```text
   user123
   user456 tech
   user789 news
   ```

   ```bash
   uv run model/import_script.py
   ```

### 2. 本地开发

**环境要求**: Python 3.13+，推荐使用 `uv` 管理依赖。

```bash
uv sync
uv run main.py
```

### 3. Docker 部署 (推荐)

1. 确保目录下有 `config.ini`（或通过环境变量配置）。
2. 启动服务：

   ```bash
   docker-compose up -d
   ```

> **注意**: 请务必在 `docker-compose.yml` 中挂载 `database.db`，否则容器重启后数据会丢失。

## ⚙️ 配置说明

本项目支持 **配置文件** 和 **环境变量** 两种方式，环境变量优先级高于配置文件。

### 核心配置

| 配置项 | 环境变量 (Docker 推荐) | 说明 |
|:--------------|:---------------------------------------|:-----------------------|
| **RSS URL** | `AUTONOTICE__RSS__RSS_BASE_URL` | RSSHub 或其他 RSS 源的基础地址 |
| **Bot Token** | `AUTONOTICE__TELEGRAM__BOT_TOKEN` | Telegram Bot API Token |
| **Chat ID** | `AUTONOTICE__TELEGRAM__TARGET_CHAT_ID` | 接收通知的 Chat ID |
| **管理员 Chat ID** | `AUTONOTICE__TELEGRAM__ADMIN_CHAT_ID` | 允许执行 Bot 命令的用户 Chat ID，留空则不限制 |
| **分组数量** | `AUTONOTICE__BASE__NUM_GROUPS` | 用户分批数量，默认 `6` |
| **每日刷新时** | `AUTONOTICE__BASE__DAILY_REFRESH_HOUR` | 每日重新分配任务的小时，默认 `23` |
| **每日刷新分** | `AUTONOTICE__BASE__DAILY_REFRESH_MINUTE` | 每日重新分配任务的分钟，默认 `50` |
| **补跑宽限** | `AUTONOTICE__BASE__MISFIRE_GRACE_SECONDS` | 错过任务的补跑最大延迟（秒），默认 `3600` |

### 调度配置

可在 `config.ini` 的 `[base]` 段或对应环境变量中调整：

| 配置项 | 默认值 | 说明 |
|:------------------------|:-------|:----------------------------------|
| `num_groups` | `6` | 将用户分成几批，每批间隔 `24/num_groups` 小时执行 |
| `daily_refresh_hour` | `23` | 每日重新分配任务的小时 |
| `daily_refresh_minute` | `50` | 每日重新分配任务的分钟 |
| `misfire_grace_seconds` | `3600` | 任务错过执行时间后允许补跑的最大延迟（秒） |

> 服务启动时会自动检测最近 1 小时内错过的任务并立即补跑。

## 💾 数据库说明

本项目使用 **SQLite** (`database.db`) 存储数据，服务启动时自动创建表结构。

- **`follower_table`**: 关注用户列表，记录最新帖子时间和上次推送时间。
- **`send_history`**: 推送历史记录，包含内容摘要和媒体快照。
- **Docker 部署请务必挂载 `/app/database.db`** 以防数据丢失。

## 🗂️ 项目结构

```
.
├── config.ini              # 配置文件 (不要提交!)
├── config.example.ini      # 配置文件模板
├── docker-compose.yml      # Docker 编排文件
├── Dockerfile              # Docker 构建文件
├── main.py                 # 入口文件 (FastAPI)
├── pyproject.toml          # 项目依赖定义
├── follower.txt            # 初始关注列表 (可选，不要提交!)
├── database.db             # SQLite 数据库 (自动生成)
├── model/                  # 数据模型与数据库操作
│   ├── model.py            # SQLModel 表定义
│   ├── follower_model.py   # 关注用户 CRUD
│   └── import_script.py    # 批量导入脚本
├── scheduler/              # 调度模块
│   └── scheduler.py        # APScheduler 任务调度 & FastAPI lifespan
├── strategy/               # 内容获取策略
│   ├── context.py          # TwitterContent 数据结构
│   ├── rss_parse.py        # RSS 解析策略
│   └── strategy_factory.py # 策略工厂（单例）
├── tg_func/                # Telegram 功能
│   ├── message_sender.py   # 消息发送（文本/图片/视频/媒体组）
│   └── commands_handller.py# Bot 命令处理与菜单注册
└── utils/                  # 工具模块
    ├── config_manager.py   # 配置管理（ini + 环境变量）
    ├── date_handler.py     # RFC 2822 日期解析与格式化
    ├── rss_client.py       # HTTP RSS 客户端
    ├── telegram_client.py  # Telegram Bot 单例管理
    └── logger.py           # 统一日志格式
```

## 🔄 CI/CD 与自动化部署

推送到 `main` 分支时，GitHub Actions 自动构建 Docker 镜像并推送至 GHCR。

```bash
# 首次登录 GHCR（只需一次）
echo $CR_PAT | docker login ghcr.io -u USERNAME --password-stdin

# 服务器拉取最新镜像并重启
docker-compose pull && docker-compose up -d
```

修改 `docker-compose.yml` 中的 `image` 字段以使用 GHCR 镜像：

```yaml
services:
  autonotice:
    image: ghcr.io/username/autonotice:latest  # 替换为你的用户名
    # build: .  <-- 本地开发时用这行，部署时注释掉
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
