import math
import json
from contextlib import asynccontextmanager
from typing import List, Tuple
from datetime import datetime, timedelta

from sqlmodel import SQLModel, select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from model.model import get_session, FollowerTable, engine, SendHistory
from strategy.context import TwitterContent
from strategy.rss_parse import RssStrategy
from strategy.strategy_factory import get_strategy
from utils.date_handler import DateHandler
from notice.message_sender import send_twitter_content
from utils.config_manager import get_config
from utils.telegram_client import get_telegram_bot, send_error_notification, get_target_chat_id
from telegram import Bot
import asyncio

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)

    # 启动定时任务
    scheduler.start()

    # 初始化任务
    refresh_daily_scheduler()

    # 获取每日刷新时间配置
    refresh_hour = get_config("base", "daily_refresh_hour", fallback=23, cast=int)
    refresh_minute = get_config("base", "daily_refresh_minute", fallback=50, cast=int)

    # 每天 23:50 (默认) 重新分配明天的任务，避开 0 点的执行高峰
    scheduler.add_job(refresh_daily_scheduler, 'cron', hour=refresh_hour, minute=refresh_minute, id='daily_refresh')

    yield

    # 关闭定时任务
    scheduler.shutdown()

def refresh_daily_scheduler():
    """
    每天刷新一次调度逻辑：
    1. 获取活跃用户总数
    2. 将用户分为 6 组 (每 4 小时一组)
    3. 为每一组创建一个定时任务
    """
    print("Refreshing daily scheduler...")
    try:
        with get_session() as session:
            # 获取活跃用户ID列表
            # 我们直接把 ID 取出来分片，而不是存 offset/limit，这样在运行期间即使用户增删也不影响当天的既定 ID 列表
            results = session.exec(
                select(FollowerTable.user_id).where(FollowerTable.category != "disable")
            ).all()
            all_user_ids = list(results)
    except Exception as e:
        print(f"Failed to refresh scheduler: {e}")
        return

    total_count = len(all_user_ids)
    if total_count == 0:
        print("No active users found.")
        return

    # 获取分组数量 (默认 6 组)
    num_groups = get_config("base", "num_groups", fallback=6, cast=int)
    # 获取过时检查时间 (默认 3600 秒)
    misfire_grace = get_config("base", "misfire_grace_seconds", fallback=3600, cast=int)

    # 1天24小时，计算每组间隔的小时数
    # 注意：如果 num_groups > 24，间隔将小于1小时，cron hour不支持小数。
    # 这里简单假设 num_groups 是 24 的约数 (1, 2, 3, 4, 6, 8, 12, 24)
    # 或者如果不整除，使用 int() 向下取整，可能导致分布不均
    hour_interval = max(1, 24 // num_groups)

    group_size = math.ceil(total_count / num_groups)

    # 清除旧的组任务 (保留 daily_refresh)
    for job in scheduler.get_jobs():
        if job.id.startswith("group_job_"):
            scheduler.remove_job(job.id)

    print(f"Scheduling {total_count} users into {num_groups} groups (approx {group_size} per group).")

    for i in range(num_groups):
        start_idx = i * group_size
        end_idx = min((i + 1) * group_size, total_count)

        if start_idx >= total_count:
            break

        group_ids = all_user_ids[start_idx:end_idx]

        # 计算启动时间：每隔 4 小时
        # 注意：如果是程序中途启动，我们希望错过的任务也能跑，或者立刻跑第一组？
        # 这里使用 interval 或者 cron 都可以。为了简单对应 "dispersed throughout the day"，
        # 我们使用 cron 固定时间点。如果当前时间超过了设定时间，APScheduler 默认策略通常是跳过或根据 misfire_grace_time 补发。
        # 这里我们设定为每 4 小时触发一次不同组。
        # 组 0 -> 0点, 组 1 -> 4点, ...
        # 注意：如果是每日 23:50 刷新任务，那么 hour=0 的任务会被安排在几分钟后的第二天 00:00 执行，衔接顺畅。
        # 如果是程序中间启动（例如中午 12:00 启动）：
        # - 0点、4点、8点的任务已错过，不会执行（除非由 misfire_grace_time 补救，这里设为 1 小时）。
        # - 12点的任务如果刚过不到 1 小时，会立即执行。
        # - 16点的任务等待执行。

        hour_trigger = i * hour_interval

        # 确保 hour 不超过 23
        if hour_trigger > 23:
             hour_trigger = hour_trigger % 24

        scheduler.add_job(
            process_group_users,
            'cron',
            hour=hour_trigger,
            minute=0, # 整点开始
            args=[group_ids, i],
            id=f"group_job_{i}",
            misfire_grace_time=misfire_grace # 允许错过一定时间内补发
        )
        print(f"Added job group_{i}: {len(group_ids)} users at {hour_trigger:02d}:00")

    # 手动检查是否有错过的任务（例如0:23启动，应补跑0:00的任务）
    now = datetime.now()
    current_hour = now.hour

    # 找到应该在最近运行的那一组
    # 每一组的 trigger 是 i * hour_interval
    for i in range(num_groups):
        trigger_hour = i * hour_interval
        if trigger_hour > 23: trigger_hour %= 24  # Normalize

        # 如果当前时间仅仅超过触发时间不到1小时（或者在grace time范围内）
        # 且我们确实错过了它（即 scheduler 刚添加的任务都是未来的）
        if trigger_hour <= current_hour < trigger_hour + 2:
            print(f"Detected missed job due to startup time (Now: {now}, Trigger: {trigger_hour}:00). Executing group {i} immediately.")
            # 重新计算该组的ID
            start_idx = i * group_size
            end_idx = min((i + 1) * group_size, total_count)
            group_ids = all_user_ids[start_idx:end_idx]

            # 立即提交任务
            scheduler.add_job(
                process_group_users,
                args=[group_ids, i],
                id=f"makeup_job_{i}_{int(datetime.now().timestamp())}",
                next_run_time=datetime.now() # 立即运行
            )


async def process_group_users(user_ids: List[str], group_index: int):
    """
    处理一组用户。
    组内每个用户请求间隔 1 分钟。
    """
    print(f"Starting Group {group_index} processing ({len(user_ids)} users).")

    # 初始化 Telegram Bot
    try:
        bot = get_telegram_bot()
    except Exception as e:
        print(f"Group {group_index}: Failed to init Telegram Bot: {e}")
        return

    # 初始化策略
    try:
        strategy = get_strategy()
    except Exception as e:
        print(f"Group {group_index}: Failed to init Strategy: {e}")
        return

    # python-telegram-bot Bot usually doesn't need context manager for simple usage unless implementing extensive connection pooling managing.
    # It manages connection pool internally. We can just use it.

    for idx, user_id in enumerate(user_ids):
        print(f"Group {group_index} - Processing {idx + 1}/{len(user_ids)}: {user_id}")

        # 处理单个用户
        try:
            # 每次重新获取 session，避免长事务
            with get_session() as session:
                follower = session.get(FollowerTable, user_id)
                if follower and follower.category != "disable":
                    # 检查最近发送时间，如果1小时内已发送过则跳过
                    if follower.latest_send_datetime and datetime.now() - follower.latest_send_datetime < timedelta(hours=1):
                        print(f"User {user_id} skipped (less than 1 hour since last check/send).")
                        continue

                    await process_follower(follower, session, bot, strategy)

                    # 更新检查时间（即使没有新内容发送，也更新检查时间，避免频繁请求）
                    # 注意：如果只是check update而没有send，是否更新latest_send_datetime?
                    # 用户的意图是“重启测试时跳过”，所以应该是指“上次处理过的时间”。
                    # 为了稳妥，我们在 process_follower 内部成功发送后更新 latest_send_datetime。
                    # 如果没有发送，那说明没有新推文，是否应该更新？
                    # 如果不更新，下次重启还会再查。RSS请求开销不大。
                    # 如果更新导致错过，那就不好了。
                    # 暂时只在 process_follower 发送成功后更新 latest_send_datetime。
                else:
                    print(f"User {user_id} skipped (not found or disabled).")
        except Exception as e:
            print(f"Error processing user {user_id} in group {group_index}: {e}")
            await send_error_notification(bot, f"Group {group_index} Error User {user_id}: {e}")

        # 组内请求间隔 1 分钟 (最后一个用户后不需要等待)
        if idx < len(user_ids) - 1:
            print(f"Group {group_index}: Waiting 60s before next user...")
            await asyncio.sleep(60)

    print(f"Group {group_index} processing finished.")


async def process_follower(follower: FollowerTable, session, bot: Bot, strategy: RssStrategy):
    print(f"Checking updates for user: {follower.user_id}")

    contents = []
    retry_count = 3
    for attempt in range(retry_count):
        try:
            contents = await strategy.get_new_media(follower.user_id)
            break
        except Exception as e:
            if attempt < retry_count - 1:
                print(f"Fetch failed for {follower.user_id}, retrying ({attempt + 1}/{retry_count})... Error: {e}")
                await asyncio.sleep(5)  # Wait before retry
            else:
                print(f"Fetch failed for {follower.user_id} after {retry_count} attempts: {e}")
                # Optional: Send error notification after all retries fail, or just log it to avoid spamming
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

    # 确定哪些是新帖子
    new_posts = []

    if last_date is None:
        print(f"First run for {follower.user_id}, sending latest post as test.")
        # 取最新的一条
        new_posts.append(valid_contents[-1])
    else:
        for content, dt in valid_contents:
            if dt > last_date:
                new_posts.append((content, dt))

    if not new_posts:
        return

    # 逐个处理新帖子
    for content, dt in new_posts:
        try:
            # 获取目标 Chat ID
            target_chat_id = get_target_chat_id()

            # 格式化时间
            post_time_str = DateHandler.format_notify(dt)

            # 发送通知 (使用新工具函数)
            await send_twitter_content(
                bot,
                content,
                target_chat_id,
                category=follower.category,
                post_time=post_time_str
            )

            # 记录历史
            media_snapshot_str = json.dumps(content.media_list) if content.media_list else None

            history = SendHistory(
                author=content.author,
                content=content.content[:200] if content.content else "", # 防止 None
                link=content.link,
                media_snapshot=media_snapshot_str,
                chat_id=str(target_chat_id),
                create_time=dt,
                send_time=datetime.now()
            )
            session.add(history)

            # 更新 Follower 状态
            follower.latest_post_datetime = dt
            follower.latest_post_link = content.link
            # 更新最近发送时间
            follower.latest_send_datetime = datetime.now()
            session.add(follower)

            session.commit()
            print(f"Successfully sent and saved update for {follower.user_id} - {content.link}")

        except Exception as e:
            print(f"Failed to send notification for {follower.user_id}: {e}")
            await send_error_notification(bot, f"发送通知失败 [{follower.user_id}]\n{content.link}\n错误: {e}")
            # 继续处理下一个帖子？还是中断？
            # 这里的策略是：单条失败不影响该用户的下一条（如果有），或者直接中断该用户的此次更新
            # 简单起见，记录错误并继续尝试（可能导致乱序如果后续成功了但这条没成功，
            # 但既然已经 sort 过了，最好是按顺序来，如果这一条失败，下一条成功会导致 latest_post_datetime 更新，
            # 从而导致这条失败的以后再也不会被发。
            # 所以：一旦失败，应该 break，停止更新该用户的状态，等待下一次轮询重试。
            break

# Removed unused/old functions: refresh_today_scheduler, get_twitter_and_push, send_telegram_notification

if __name__ == '__main__':
    refresh_daily_scheduler()
