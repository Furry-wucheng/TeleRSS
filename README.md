# TeleRSS

AutoNotice 是一个自动化的通知服务，旨在通过 RSS 或直接请求的方式监控信息源，并推送到 Telegram。

## ✨ 特性

- **多源支持**: 目前支持 RSS 订阅源监控。
- **消息推送**: 集成 Telegram Bot 推送通知。
- **容器化**: 提供 Docker 支持，便于部署。
- **配置灵活**: 支持配置文件 (`config.ini`) 和环境变量双重配置。
- **任务调度**: 支持分批次任务执行，避免集中请求压力。

## 🚀 快速开始

### 1. 准备工作 (重要!)

在开始之前，您需要手动准备关注列表文件和配置文件。

1. **准备配置文件**:

   ```bash
   cp config.example.ini config.ini
   # 编辑 config.ini 填入 RSS URL 和 Telegram Token
   ```
2. **准备关注列表**:
   创建一个名为 `follower.txt` 的文件，填入您想监控的 RSS 订阅源 ID 或标识符。
   格式说明：

   - 每行一个用户ID
   - 可选：`用户ID 分类` (用空格分隔)

   **示例 `follower.txt`**:

   ```text
   user123
   user456 tech
   user789 news
   ```

   *注意：目前版本需要在启动前手动准备此文件。后续版本将支持自动爬取关注列表并存入数据库。*
3. **部署或者找开放的RssHub**:
   目前服务依赖RSShub进行获取信息，更考虑后续可能会有其他平台（例如微博），所以更推荐使用RSSHub，部署教程可以去[我的博客](https://blog.wucheng.work)查看（现在可能没写好）。

### 2. 本地开发

**环境要求**: Python 3.13+，推荐使用 `uv` 管理依赖。

```bash
# 安装依赖
uv sync

# 运行 (会自动根据 follower.txt 初始化数据库)
uv run main.py
```

### 3. Docker 部署 (推荐)

项目包含 `Dockerfile` 和 `docker-compose.yml`，可直接一键启动。

1. **准备文件**:
   确保目录下有 `config.ini` 和 `follower.txt`。
2. **启动服务**:

   ```bash
   docker-compose up -d
   ```

## ⚙️ 配置说明

本项目支持 **配置文件** 和 **环境变量** 两种方式。环境变量优先级高于配置文件。

### 核心配置

| 配置项              | 环境变量 (Docker推荐)                    | 说明                           |
| :------------------ | :--------------------------------------- | :----------------------------- |
| **RSS URL**   | `AUTONOTICE__RSS__RSS_BASE_URL`        | RSSHub 或其他 RSS 源的基础地址 |
| **Bot Token** | `AUTONOTICE__TELEGRAM__BOT_TOKEN`      | Telegram Bot API Token         |
| **Chat ID**   | `AUTONOTICE__TELEGRAM__TARGET_CHAT_ID` | 接收通知的 Chat ID             |

### 调度配置 (Scheduler)

可在 `config.ini` 的 `[base]` 字段中调整：

- **分批数量 (`num_groups`)**: 默认为 6。将总用户分成几批在一天内执行。例如6批意味着每隔4小时执行一批。
- **每日刷新时间 (`daily_refresh_hour`/`minute`)**: 默认为 23:50。重新加载用户列表并在次日重新分配任务的时间。
- **超时检查 (`misfire_grace_seconds`)**: 默认为 3600秒 (1小时)。如果任务错过预定时间（如重启服务），允许补发的最大延迟。

## 💾 数据库说明

本项目使用 **SQLite** (`database.db`) 存储数据。

- **初始化**: 目前程序启动时会根据 `follower.txt` 自动检查并导入新用户到数据库 (通过 `import_script.py` 或启动逻辑)。
- **持久化**: Docker 部署时请务必挂载 `/app/database.db` 以防数据丢失。
- **未来计划**:
  - [ ] 实现自动从源站爬取关注列表并更新数据库。
  - [ ] 提供管理 API 以动态添加/删除关注者。

## � CI/CD 与自动化部署

本项目支持通过 GitHub Actions 自动构建 Docker 镜像并推送至 GHCR (GitHub Container Registry)。

### 1. 部署流程

1. **提交代码**: 当您将代码推送到 `main` 分支时，GitHub Actions 会自动触发构建。
2. **构建镜像**: 系统会自动构建最新的 Docker 镜像 `ghcr.io/您的用户名/autonotice:latest`。
3. **服务器更新**:
   在您的服务器上，使用以下命令更新并运行最新版本：

   **前置条件**: 首次拉取镜像前，需要登录 GitHub Container Registry (只需一次):

   ```bash
   # 使用您的 GitHub 用户名和 Personal Access Token (PAT)
   echo $CR_PAT | docker login ghcr.io -u USERNAME --password-stdin
   ```

   **更新与启动**:

   ```bash
   # 1. 拉取最新镜像
   docker-compose pull

   # 2. 重启服务 (旧容器被替换，但数据因挂载而保留)
   docker-compose up -d
   ```

### 2. 修改 `docker-compose.yml` (重要)

为了使用 GitHub 构建的镜像，您需要修改 `docker-compose.yml` 中的 `image` 字段：

```yaml
services:
  autonotice:
    # 替换为您的 GitHub 用户名和小写的仓库名
    image: ghcr.io/username/autonotice:latest
    # build: .  <-- 开发时用 build，部署时注释掉这行
    container_name: autonotice
    # ... 其他配置保持不变 ...
```

## 🀽� 项目结构

```
.
├── config.ini          # 配置文件 (不要提交!)
├── config.example.ini  # 配置文件模板 (提交这个)
├── docker-compose.yml  # Docker 编排文件
├── Dockerfile          # Docker 构建文件
├── main.py             # 入口文件
├── pyproject.toml      # 项目依赖定义
├── follower.txt        # 关注列表数据 (不要提交!)
├── database.db         # SQLite 数据库 (自动生成)
├── notice/             # 通知模块
├── scheduler/          # 调度模块
├── strategy/           # 策略模块
└── utils/              # 工具模块
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
