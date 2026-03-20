"""
researcher.py - ネタ収集エージェント
- YouTube Data APIでキーワード検索
- theme_tree.jsonを参照してデータが少ないテーマを優先
- 動画の説明文・タイトルからネタ候補を抽出してJSONに保存
- 1回の実行で10〜20件のネタをdata/research_pool.jsonに追加
"""

import json
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
RESEARCH_POOL_FILE = DATA_DIR / "research_pool.json"
SUPERVISOR_LOG_FILE = DATA_DIR / "supervisor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RESEARCHER] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(SUPERVISOR_LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

SEARCH_KEYWORDS = [
    "副業 始め方",
    "スマホ副業 稼げない",
    "副業 初心者 おすすめ",
    "副業 会社バレ 対策",
    "副業 月5万",
    "節約術 会社員",
    "投資 入門 初心者",
    "副業 失敗 体験談",
    "副業 詐欺 見分け方",
    "時間 副業 スキマ時間",
]


def load_config():
    with open(BASE_DIR / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_theme_tree():
    with open(KNOWLEDGE_DIR / "theme_tree.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_research_pool():
    if not RESEARCH_POOL_FILE.exists():
        return []
    with open(RESEARCH_POOL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_research_pool(pool: list):
    with open(RESEARCH_POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)


def get_theme_coverage(pool: list, theme_tree: dict) -> dict:
    """各テーマのネタ件数を集計"""
    coverage = {}
    for category, themes in theme_tree.items():
        for theme in themes:
            key = f"{category}/{theme}"
            coverage[key] = sum(1 for item in pool if item.get("theme") == key)
    return coverage


def select_priority_themes(coverage: dict, count: int = 5) -> list:
    """データが少ないテーマを優先的に選択"""
    sorted_themes = sorted(coverage.items(), key=lambda x: x[1])
    return [theme for theme, _ in sorted_themes[:count]]


def search_youtube(api_key: str, keyword: str, max_results: int = 10) -> list:
    """YouTube Data APIでキーワード検索"""
    if requests is None:
        logger.error("requests module not installed. Run: pip install requests")
        return []

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "maxResults": max_results,
        "key": api_key,
        "relevanceLanguage": "ja",
        "regionCode": "JP",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])
    except Exception as e:
        logger.error(f"YouTube API error for keyword '{keyword}': {e}")
        return []


def extract_ideas_from_video(video: dict, theme: str) -> Optional[dict]:
    """動画のタイトル・説明文からネタを抽出"""
    snippet = video.get("snippet", {})
    title = snippet.get("title", "")
    description = snippet.get("description", "")
    video_id = video.get("id", {}).get("videoId", "")

    if not title:
        return None

    return {
        "id": f"R{datetime.now().strftime('%Y%m%d%H%M%S')}_{video_id[:6]}",
        "theme": theme,
        "source": "youtube",
        "video_id": video_id,
        "title": title,
        "description": description[:500],
        "keywords": extract_keywords(title + " " + description),
        "collected_at": datetime.now().isoformat(),
        "used": False,
    }


def extract_keywords(text: str) -> list:
    """簡易キーワード抽出"""
    important_terms = [
        "副業", "稼ぐ", "収入", "月収", "節約", "投資", "失敗", "詐欺",
        "初心者", "始め方", "おすすめ", "スマホ", "スキマ時間", "確定申告",
        "会社", "バレ", "継続", "マインド", "ポイント", "固定費"
    ]
    found = [term for term in important_terms if term in text]
    return found


def run(target_count: int = 15):
    """メイン実行関数"""
    logger.info("=== Researcher Started ===")

    config = load_config()
    api_key = config["youtube_api"]["api_key"]

    if api_key.startswith("【"):
        logger.warning("YouTube API key not configured. Using mock data.")
        return run_mock(target_count)

    theme_tree = load_theme_tree()
    pool = load_research_pool()
    coverage = get_theme_coverage(pool, theme_tree)
    priority_themes = select_priority_themes(coverage, count=5)

    logger.info(f"Priority themes: {priority_themes}")

    new_ideas = []
    for theme in priority_themes:
        category = theme.split("/")[0]
        sub_theme = theme.split("/")[1] if "/" in theme else theme
        keyword = f"{sub_theme} 副業" if "副業" not in sub_theme else sub_theme

        videos = search_youtube(api_key, keyword, max_results=4)
        for video in videos:
            idea = extract_ideas_from_video(video, theme)
            if idea:
                new_ideas.append(idea)

    # 追加のキーワードで補充
    if len(new_ideas) < target_count:
        for keyword in SEARCH_KEYWORDS[:3]:
            videos = search_youtube(api_key, keyword, max_results=3)
            for video in videos:
                theme = f"副業入門/副業の選び方"
                idea = extract_ideas_from_video(video, theme)
                if idea:
                    new_ideas.append(idea)
            if len(new_ideas) >= target_count:
                break

    # 重複排除（video_idベース）
    existing_ids = {item.get("video_id") for item in pool}
    new_ideas = [i for i in new_ideas if i.get("video_id") not in existing_ids]

    pool.extend(new_ideas)
    save_research_pool(pool)

    logger.info(f"Added {len(new_ideas)} new ideas. Total pool: {len(pool)}")
    logger.info("=== Researcher Completed ===")
    return new_ideas


def run_mock(target_count: int = 15):
    """APIキー未設定時のモックデータ生成"""
    logger.info("Running in mock mode (no API key)")

    mock_ideas = [
        {
            "id": f"MOCK_{i:03d}",
            "theme": "副業入門/副業の選び方",
            "source": "mock",
            "video_id": f"mock_{i:03d}",
            "title": f"副業初心者が最初にやるべきこと【サンプル{i}】",
            "description": "副業を始めたい人向けのサンプルコンテンツです。",
            "keywords": ["副業", "初心者", "始め方"],
            "collected_at": datetime.now().isoformat(),
            "used": False,
        }
        for i in range(1, target_count + 1)
    ]

    pool = load_research_pool()
    pool.extend(mock_ideas)
    save_research_pool(pool)

    logger.info(f"Added {len(mock_ideas)} mock ideas.")
    return mock_ideas


if __name__ == "__main__":
    result = run()
    print(f"Collected {len(result)} ideas.")
