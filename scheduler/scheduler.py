import math
from contextlib import asynccontextmanager
from typing import List, Tuple
from datetime import datetime, timedelta

from sqlmodel import SQLModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from model.model import async_engine, FollowerTable
from model import follower_model
from strategy.context import TwitterContent
from strategy.rss_parse import RssStrategy
from strategy.strategy_factory import get_strategy
from utils.date_handler import DateHandler
from tg_func.message_sender import send_twitter_content
from tg_func.commands_handller import setup_commands
from utils.config_manager import get_config
from utils.logger import get_logger
from utils.telegram_client import get_telegram_bot, get_telegram_application, send_error_notification, get_target_chat_id
from telegram import Bot
import asyncio

logger = get_logger(__name__)
scheduler = AsyncIOScheduler()


# ---------------------------------------------------------------------------
# lifespan & scheduler setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Initialize Telegram Bot Application
    tg_app = get_telegram_application()
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    await setup_commands(tg_app)

    # 启动定时任务
    scheduler.start()

    # 初始化任务
    await refresh_daily_scheduler()

    # 获取每日刷新时间配置
    refresh_hour = get_config("base", "daily_refresh_hour", fallback=23, cast=int)
    refresh_minute = get_config("base", "daily_refresh_minute", fallback=50, cast=int)

    # 每天 23:50 (默认) 重新分配明天的任务，避开 0 点的执行高峰
    scheduler.add_job(refresh_daily_scheduler, 'cron', hour=refresh_hour, minute=refresh_minute, id='daily_refresh')

    yield

    # Stop Telegram Bot Application
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()

    scheduler.shutdown()


async def refresh_daily_scheduler():
    """
    每天刷新一次调度逻辑：
    1. 获取活跃用户总数
    2. 将用户分为 N 组 (每组间隔若干小时)
    3. 为每一组创建一个定时任务
    """
    logger.info("Refreshing daily scheduler...")
    try:
        all_user_ids = await follower_model.get_active_user_ids()
    except Exception as e:
        logger.error(f"Failed to refresh scheduler: {e}")
        return

    total_count = len(all_user_ids)
    if total_count == 0:
        logger.warning("No active users found.")
        return

    num_groups = get_config("base", "num_groups", fallback=6, cast=int)
    misfire_grace = get_config("base", "misfire_grace_seconds", fallback=3600, cast=int)
    hour_interval = max(1, 24 // num_groups)
    group_size = math.ceil(total_count / num_groups)

    # 清除旧的组任务 (保留 daily_refresh)
    for job in scheduler.get_jobs():
        if job.id.startswith("group_job_"):
            scheduler.remove_job(job.id)

    logger.info(f"Scheduling {total_count} users into {num_groups} groups (approx {group_size} per group).")

    for i in range(num_groups):
        start_idx = i * group_size
        end_idx = min((i + 1) * group_size, total_count)

        if start_idx >= total_count:
            break

        group_ids = all_user_ids[start_idx:end_idx]
        hour_trigger = (i * hour_interval) % 24

        scheduler.add_job(
            process_group_users,
            'cron',
            hour=hour_trigger,
            minute=0,
            args=[group_ids, i],
            id=f"group_job_{i}",
            misfire_grace_time=misfire_grace
        )
        logger.info(f"Added job group_{i}: {len(group_ids)} users at {hour_trigger:02d}:00")

    # 手动补跑：检查启动时是否有刚错过的组（2小时内）
    now = datetime.now()
    current_hour = now.hour

    for i in range(num_groups):
        trigger_hour = (i * hour_interval) % 24
        if trigger_hour <= current_hour < trigger_hour + 2:
            logger.info(f"Detected missed job (Now: {now}, Trigger: {trigger_hour}:00). Executing group {i} immediately.")
            start_idx = i * group_size
            end_idx = min((i + 1) * group_size, total_count)
            group_ids = all_user_ids[start_idx:end_idx]
            scheduler.add_job(
                process_group_users,
                'date',
                args=[group_ids, i],
                id=f"makeup_job_{i}_{int(now.timestamp())}",
                next_run_time=now
            )


# ---------------------------------------------------------------------------
# 异步任务处理（直接 await DB 函数）
# ---------------------------------------------------------------------------

async def process_group_users(user_ids: List[str], group_index: int):
    """
    处理一组用户，组内每个用户请求间隔 1 分钟。
    """
    logger.info(f"Starting Group {group_index} processing ({len(user_ids)} users).")

    try:
        bot = get_telegram_bot()
    except Exception as e:
        logger.error(f"Group {group_index}: Failed to init Telegram Bot: {e}")
        return

    try:
        strategy = get_strategy()
    except Exception as e:
        logger.error(f"Group {group_index}: Failed to init Strategy: {e}")
        return

    for idx, user_id in enumerate(user_ids):
        logger.info(f"Group {group_index} - Processing {idx + 1}/{len(user_ids)}: {user_id}")

        try:
            follower = await follower_model.get_follower_snapshot(user_id)

            if follower and follower.category != "disable":
                if follower.latest_send_datetime and datetime.now() - follower.latest_send_datetime < timedelta(hours=1):
                    logger.info(f"User {user_id} skipped (less than 1 hour since last check/send).")
                    continue
                await process_follower(follower, bot, strategy)
            else:
                logger.info(f"User {user_id} skipped (not found or disabled).")
        except Exception as e:
            logger.error(f"Error processing user {user_id} in group {group_index}: {e}")
            await send_error_notification(bot, f"Group {group_index} Error User {user_id}: {e}")

        if idx < len(user_ids) - 1:
            logger.debug(f"Group {group_index}: Waiting 60s before next user...")
            await asyncio.sleep(60)

    logger.info(f"Group {group_index} processing finished.")


async def process_follower(follower: FollowerTable, bot: Bot, strategy: RssStrategy):
    logger.info(f"Checking updates for user: {follower.user_id}")

    contents = []
    retry_count = 3
    for attempt in range(retry_count):
        try:
            contents = await strategy.get_new_media(follower.user_id)
            break
        except Exception as e:
            if attempt < retry_count - 1:
                logger.warning(f"Fetch failed for {follower.user_id}, retrying ({attempt + 1}/{retry_count})... Error: {e}")
                await asyncio.sleep(5)
            else:
                logger.error(f"Fetch failed for {follower.user_id} after {retry_count} attempts: {e}")
                await send_error_notification(bot, f"Fetch failed for {follower.user_id}: {e}")
                return

    if not contents:
        return

    # 解析日期并验证
    valid_contents: List[Tuple[TwitterContent, datetime]] = []
    for c in contents:
        dt = DateHandler.parse_rfc2822(c.publish_date)
        if dt:
            valid_contents.append((c, dt))

    if not valid_contents:
        return

    # 按时间升序排序（旧 -> 新）
    valid_contents.sort(key=lambda x: x[1])

    last_date = follower.latest_post_datetime

    new_posts: List[Tuple[TwitterContent, datetime]] = []
    if last_date is None:
        logger.info(f"First run for {follower.user_id}, sending latest post as test.")
        new_posts.append(valid_contents[-1])
    else:
        for content, dt in valid_contents:
            if dt > last_date:
                new_posts.append((content, dt))

    if not new_posts:
        return

    for content, dt in new_posts:
        try:
            target_chat_id = get_target_chat_id()
            post_time_str = DateHandler.format_notify(dt)

            # 发送 Telegram 通知（纯异步，不阻塞）
            await send_twitter_content(
                bot,
                content,
                target_chat_id,
                category=follower.category,
                post_time=post_time_str
            )

            # 直接 await 异步 DB 写入
            await follower_model.save_post_result(
                follower.user_id,
                content,
                dt,
                str(target_chat_id),
            )

            logger.info(f"Successfully sent and saved update for {follower.user_id} - {content.link}")

        except Exception as e:
            logger.error(f"Failed to send notification for {follower.user_id}: {e}")
            await send_error_notification(bot, f"发送通知失败 [{follower.user_id}]\n{content.link}\n错误: {e}")
            # 一旦失败，停止更新该用户状态，等待下次轮询重试
            break


if __name__ == '__main__':
    asyncio.run(refresh_daily_scheduler())
