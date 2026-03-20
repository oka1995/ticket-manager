"""
fetcher.py - データ取得エージェント
- 投稿から24時間後にThreads APIからメトリクスを取得
- 閲覧数・いいね・リプライ・シェア数をpost_history.jsonに追記
- 1日1回 02:00に実行
"""

import json
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
POST_HISTORY_FILE = DATA_DIR / "post_history.json"
SUPERVISOR_LOG_FILE = DATA_DIR / "supervisor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FETCHER] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(SUPERVISOR_LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def load_config():
    with open(BASE_DIR / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_post_history() -> list:
    if not POST_HISTORY_FILE.exists():
        return []
    with open(POST_HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_post_history(history: list):
    with open(POST_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def is_ready_for_metrics(post: dict, hours_after: int = 24) -> bool:
    """投稿からhours_after時間以上経過しているか確認"""
    posted_at = post.get("posted_at")
    if not posted_at:
        return False

    try:
        post_time = datetime.fromisoformat(posted_at)
        elapsed = datetime.now() - post_time
        return elapsed >= timedelta(hours=hours_after)
    except Exception:
        return False


def fetch_metrics_from_api(api_config: dict, post_id: str) -> Optional[dict]:
    """Threads APIからメトリクスを取得"""
    if requests is None:
        logger.error("requests module not installed")
        return None

    access_token = api_config.get("access_token", "")
    if access_token.startswith("【"):
        return generate_mock_metrics(post_id)

    url = f"https://graph.threads.net/v1.0/{post_id}/insights"
    params = {
        "metric": "views,likes,replies,reposts,quotes",
        "access_token": access_token,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        metrics = {}
        for item in data.get("data", []):
            name = item.get("name")
            values = item.get("values", [])
            if values:
                metrics[name] = values[-1].get("value", 0)

        return {
            "views": metrics.get("views", 0),
            "likes": metrics.get("likes", 0),
            "replies": metrics.get("replies", 0),
            "shares": metrics.get("reposts", 0) + metrics.get("quotes", 0),
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching metrics for post {post_id}: {e}")
        return None


def generate_mock_metrics(post_id: str) -> dict:
    """モックメトリクスを生成（APIキー未設定時）"""
    import random
    return {
        "views": random.randint(100, 5000),
        "likes": random.randint(5, 200),
        "replies": random.randint(0, 30),
        "shares": random.randint(0, 20),
        "fetched_at": datetime.now().isoformat(),
        "is_mock": True,
    }


def run():
    """メイン実行関数"""
    logger.info("=== Fetcher Started ===")

    config = load_config()
    api_config = config["threads_api"]

    history = load_post_history()
    updated_count = 0

    for i, post in enumerate(history):
        # 既にメトリクスがある場合はスキップ
        if post.get("metrics") and not post["metrics"].get("is_mock"):
            continue

        # 投稿成功かつ24時間以上経過した投稿のみ取得
        if post.get("status") != "success":
            continue

        if not is_ready_for_metrics(post):
            continue

        post_id = post.get("post_id")
        if not post_id:
            continue

        logger.info(f"Fetching metrics for post: {post_id}")
        metrics = fetch_metrics_from_api(api_config, post_id)

        if metrics:
            history[i]["metrics"] = metrics
            updated_count += 1
            logger.info(
                f"Metrics updated: views={metrics['views']}, "
                f"likes={metrics['likes']}, replies={metrics['replies']}"
            )
        else:
            logger.warning(f"Failed to fetch metrics for post: {post_id}")

        # APIレート制限対策
        time.sleep(0.5)

    save_post_history(history)
    logger.info(f"Updated metrics for {updated_count} posts.")
    logger.info("=== Fetcher Completed ===")
    return updated_count


if __name__ == "__main__":
    count = run()
    print(f"Fetched metrics for {count} post(s).")
