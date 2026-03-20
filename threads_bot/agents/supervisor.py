"""
supervisor.py - 監視・異常検知エージェント
- エラー連続3回で全処理停止
- kill_switch.flag チェック
- 1日の投稿上限チェック
- 最低投稿間隔チェック
"""

import json
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
KILL_SWITCH_FLAG = DATA_DIR / "kill_switch.flag"
POST_HISTORY_FILE = DATA_DIR / "post_history.json"
ERROR_LOG_FILE = DATA_DIR / "error.log"
SUPERVISOR_LOG_FILE = DATA_DIR / "supervisor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SUPERVISOR] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(SUPERVISOR_LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def load_config():
    with open(BASE_DIR / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_post_history():
    if not POST_HISTORY_FILE.exists():
        return []
    with open(POST_HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def check_kill_switch():
    """kill_switch.flagが存在する場合は即停止"""
    if KILL_SWITCH_FLAG.exists():
        logger.warning("Kill switch is active. Stopping all processes.")
        sys.exit(1)


def check_consecutive_errors():
    """直近のエラーログを確認し、3回連続エラーなら停止"""
    if not ERROR_LOG_FILE.exists():
        return False

    with open(ERROR_LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 直近10件のログを確認
    recent = lines[-10:] if len(lines) >= 10 else lines
    error_count = sum(1 for line in recent if "[ERROR]" in line)

    # 連続エラーカウント
    consecutive = 0
    for line in reversed(recent):
        if "[ERROR]" in line:
            consecutive += 1
        else:
            break

    if consecutive >= 3:
        logger.error(f"Consecutive errors detected ({consecutive}). Auto-stopping system.")
        return True
    return False


def check_daily_post_limit():
    """本日の投稿数が上限を超えていないか確認"""
    config = load_config()
    daily_limit = config["settings"]["daily_post_limit"]
    history = load_post_history()

    today = datetime.now().strftime("%Y-%m-%d")
    today_posts = [
        p for p in history
        if p.get("posted_at", "").startswith(today) and p.get("status") == "success"
    ]

    count = len(today_posts)
    logger.info(f"Today's post count: {count}/{daily_limit}")

    if count >= daily_limit:
        logger.warning(f"Daily post limit reached ({count}/{daily_limit}). Queuing remaining posts.")
        return False
    return True


def check_min_interval():
    """最後の投稿から最低投稿間隔が経過しているか確認"""
    config = load_config()
    min_interval = config["settings"]["min_interval_minutes"]
    history = load_post_history()

    successful = [p for p in history if p.get("status") == "success"]
    if not successful:
        return True

    # 最新の投稿時刻を確認
    last_post = max(successful, key=lambda p: p.get("posted_at", ""))
    last_time_str = last_post.get("posted_at", "")

    try:
        last_time = datetime.fromisoformat(last_time_str)
        elapsed = (datetime.now() - last_time).total_seconds() / 60
        if elapsed < min_interval:
            logger.warning(
                f"Minimum interval not met. Last post: {elapsed:.1f} min ago "
                f"(minimum: {min_interval} min)"
            )
            return False
    except Exception as e:
        logger.error(f"Error parsing last post time: {e}")

    return True


def check_missed_posts():
    """予定投稿が実行されなかった場合の確認"""
    POST_QUEUE_FILE = DATA_DIR / "post_queue.json"
    if not POST_QUEUE_FILE.exists():
        return

    with open(POST_QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    now = datetime.now()
    for post in queue:
        scheduled_str = post.get("scheduled_at")
        if not scheduled_str:
            continue
        try:
            scheduled = datetime.fromisoformat(scheduled_str)
            if scheduled < now - timedelta(hours=2):
                logger.warning(
                    f"Missed scheduled post: id={post.get('id')}, "
                    f"scheduled={scheduled_str}"
                )
        except Exception:
            pass


def run_system_check():
    """全システムチェックを実行"""
    logger.info("=== System Check Started ===")

    # Kill switch確認
    check_kill_switch()

    # 連続エラー確認
    if check_consecutive_errors():
        logger.error("System auto-stopped due to consecutive errors.")
        sys.exit(1)

    # 日次投稿上限確認
    within_limit = check_daily_post_limit()

    # 最低投稿間隔確認
    interval_ok = check_min_interval()

    # 未実行投稿の確認
    check_missed_posts()

    logger.info("=== System Check Completed ===")
    return {
        "within_daily_limit": within_limit,
        "interval_ok": interval_ok,
        "kill_switch": False,
        "consecutive_errors": False,
    }


def log_error(message: str):
    """エラーをログに記録"""
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} [ERROR] {message}\n")


def log_info(message: str):
    """情報をログに記録"""
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} [INFO] {message}\n")


if __name__ == "__main__":
    result = run_system_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
