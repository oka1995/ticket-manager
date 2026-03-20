"""
poster.py - 投稿実行エージェント
- post_queue.jsonから投稿を取り出してThreads APIで投稿
- cronで所定のタイムスロットに分散
- コメント誘導型・ツリー型・アフィリエイト型の特殊処理
- 投稿成功・失敗をpost_history.jsonに記録
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
POST_QUEUE_FILE = DATA_DIR / "post_queue.json"
POST_HISTORY_FILE = DATA_DIR / "post_history.json"
KILL_SWITCH_FLAG = DATA_DIR / "kill_switch.flag"
SUPERVISOR_LOG_FILE = DATA_DIR / "supervisor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [POSTER] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(SUPERVISOR_LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# 投稿タイムスロット（時間）
POST_TIME_SLOTS = [8, 10, 12, 14, 16, 19, 20, 22, 23, 1]


def load_config():
    with open(BASE_DIR / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_json(path: Path) -> any:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_kill_switch():
    if KILL_SWITCH_FLAG.exists():
        logger.warning("Kill switch detected. Stopping poster.")
        sys.exit(0)


def get_current_slot() -> Optional[int]:
    """現在の時刻が投稿スロットに該当するか確認（±10分の余裕）"""
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute

    for slot_hour in POST_TIME_SLOTS:
        # 時間の差を計算（0-23の循環を考慮）
        diff = (current_hour * 60 + current_minute) - slot_hour * 60
        if abs(diff) <= 10 or abs(diff - 1440) <= 10:
            return slot_hour

    return None


def check_daily_limit(history: list, daily_limit: int) -> bool:
    """本日の投稿数が上限以内か確認"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = sum(
        1 for p in history
        if p.get("posted_at", "").startswith(today) and p.get("status") == "success"
    )
    if today_count >= daily_limit:
        logger.warning(f"Daily limit reached: {today_count}/{daily_limit}")
        return False
    return True


def check_min_interval(history: list, min_minutes: int) -> bool:
    """最低投稿間隔を確認"""
    successful = [p for p in history if p.get("status") == "success"]
    if not successful:
        return True

    last = max(successful, key=lambda p: p.get("posted_at", ""))
    try:
        last_time = datetime.fromisoformat(last["posted_at"])
        elapsed = (datetime.now() - last_time).total_seconds() / 60
        if elapsed < min_minutes:
            logger.warning(f"Min interval not met: {elapsed:.1f} min elapsed (min: {min_minutes} min)")
            return False
    except Exception:
        pass

    return True


def create_threads_post(api_config: dict, text: str) -> Optional[dict]:
    """Threads APIで投稿を作成（コンテナ作成）"""
    if requests is None:
        logger.error("requests module not installed")
        return None

    user_id = api_config["user_id"]
    access_token = api_config["access_token"]

    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": access_token,
    }

    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Threads API error (create container): {e}")
        return None


def publish_threads_post(api_config: dict, creation_id: str) -> Optional[dict]:
    """Threads APIで投稿を公開"""
    if requests is None:
        return None

    user_id = api_config["user_id"]
    access_token = api_config["access_token"]

    url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    params = {
        "creation_id": creation_id,
        "access_token": access_token,
    }

    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Threads API error (publish): {e}")
        return None


def post_reply(api_config: dict, post_id: str, text: str) -> Optional[dict]:
    """返信投稿（コメント欄への投稿）"""
    if requests is None:
        return None

    user_id = api_config["user_id"]
    access_token = api_config["access_token"]

    # コンテナ作成（返信として）
    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "reply_to_id": post_id,
        "access_token": access_token,
    }

    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        container = response.json()
        creation_id = container.get("id")
        if not creation_id:
            return None

        # 公開
        time.sleep(1)
        return publish_threads_post(api_config, creation_id)
    except Exception as e:
        logger.error(f"Threads API error (reply): {e}")
        return None


def post_to_threads(api_config: dict, post: dict) -> tuple[bool, Optional[str]]:
    """投稿を実行してpost_idを返す"""
    access_token = api_config.get("access_token", "")

    # APIキー未設定の場合はモック
    if access_token.startswith("【"):
        logger.info(f"[MOCK] Would post: {post['content'][:50]}...")
        mock_id = f"mock_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return True, mock_id

    # コンテナ作成
    container = create_threads_post(api_config, post["content"])
    if not container:
        return False, None

    creation_id = container.get("id")
    if not creation_id:
        return False, None

    # 少し待ってから公開
    time.sleep(2)

    # 公開
    result = publish_threads_post(api_config, creation_id)
    if not result:
        return False, None

    post_id = result.get("id")
    return True, post_id


def handle_comment_post(api_config: dict, post: dict, post_id: str):
    """コメント誘導型・ツリー型・アフィリエイト型の追加処理"""
    pattern_id = post.get("pattern_id")

    # コメント誘導型（P07）: 続きをコメント欄に
    if pattern_id == "P07":
        comment_text = "↑コメントで教えてください！皆の意見が聞きたい。"
        post_reply(api_config, post_id, comment_text)
        logger.info(f"Added comment for P07 post: {post_id}")

    # ツリー展開型（P09）: 続きを返信で
    elif pattern_id == "P09":
        continuation = post.get("tree_continuation")
        if continuation:
            post_reply(api_config, post_id, continuation)
            logger.info(f"Added tree continuation for P09 post: {post_id}")

    # アフィリエイト誘導型（P15）: コメント欄にPRリンク
    elif pattern_id == "P15" or post.get("is_affiliate"):
        affiliate_comment = post.get("affiliate_comment",
            "詳しい情報はこちら→（リンクをプロフィールに貼っています）\n\n※PRを含む場合あり")
        post_reply(api_config, post_id, affiliate_comment)
        logger.info(f"Added affiliate comment for post: {post_id}")


def run(force: bool = False):
    """メイン実行関数"""
    logger.info("=== Poster Started ===")

    check_kill_switch()

    config = load_config()
    api_config = config["threads_api"]
    daily_limit = config["settings"]["daily_post_limit"]
    min_interval = config["settings"]["min_interval_minutes"]

    # 投稿スロットチェック（forceでない場合）
    if not force:
        current_slot = get_current_slot()
        if current_slot is None:
            logger.info("Not in a posting time slot. Skipping.")
            return []

    queue = load_json(POST_QUEUE_FILE)
    history = load_json(POST_HISTORY_FILE)

    # 日次上限チェック
    if not check_daily_limit(history, daily_limit):
        return []

    # 最低投稿間隔チェック
    if not check_min_interval(history, min_interval):
        return []

    # キューから次の投稿を取得
    pending = [p for p in queue if p.get("status") == "queued"]
    if not pending:
        logger.info("No posts in queue.")
        return []

    post = pending[0]
    logger.info(f"Posting: id={post['id']}, pattern={post.get('pattern_name')}, theme={post.get('theme')}")

    # 投稿実行
    success, post_id = post_to_threads(api_config, post)
    posted_at = datetime.now().isoformat()

    # ステータス更新
    if success:
        post["status"] = "success"
        post["post_id"] = post_id
        post["posted_at"] = posted_at
        logger.info(f"Post successful: id={post_id}")

        # 特殊処理（コメント欄への投稿など）
        if post_id:
            handle_comment_post(api_config, post, post_id)
    else:
        post["status"] = "failed"
        post["posted_at"] = posted_at
        logger.error(f"Post failed: {post['id']}")

    # キューとヒストリーを更新
    queue = [p if p["id"] != post["id"] else post for p in queue]

    history_entry = {
        "id": post["id"],
        "post_id": post.get("post_id"),
        "content": post["content"],
        "theme": post.get("theme"),
        "pattern_id": post.get("pattern_id"),
        "pattern_name": post.get("pattern_name"),
        "is_affiliate": post.get("is_affiliate", False),
        "scores": post.get("scores"),
        "created_at": post.get("created_at"),
        "posted_at": posted_at,
        "status": post["status"],
        "metrics": None,  # fetcher.pyが後で埋める
    }
    history.append(history_entry)

    save_json(POST_QUEUE_FILE, queue)
    save_json(POST_HISTORY_FILE, history)

    logger.info("=== Poster Completed ===")
    return [post] if success else []


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force post regardless of time slot")
    args = parser.parse_args()

    result = run(force=args.force)
    print(f"Posted {len(result)} post(s).")
