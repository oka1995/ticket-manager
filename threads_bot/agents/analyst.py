"""
analyst.py - パフォーマンス分析エージェント
- post_history.jsonから過去投稿のメトリクスを読み込む
- 閲覧数・いいね・リプライで投稿をスコアリング
- 「伸びたパターン」「伸びなかったテーマ」を分析
- 分析結果をdata/analyst_feedback.jsonに書き出す（ライターへの指示書）
"""

import json
import sys
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
POST_HISTORY_FILE = DATA_DIR / "post_history.json"
ANALYTICS_FILE = DATA_DIR / "analytics.json"
ANALYST_FEEDBACK_FILE = DATA_DIR / "analyst_feedback.json"
SUPERVISOR_LOG_FILE = DATA_DIR / "supervisor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ANALYST] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(SUPERVISOR_LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def load_post_history() -> list:
    if not POST_HISTORY_FILE.exists():
        return []
    with open(POST_HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_analytics(data: dict):
    with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_analyst_feedback(data: dict):
    with open(ANALYST_FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calculate_post_score(post: dict) -> float:
    """投稿のエンゲージメントスコアを計算"""
    metrics = post.get("metrics", {})
    views = metrics.get("views", 0)
    likes = metrics.get("likes", 0)
    replies = metrics.get("replies", 0)
    shares = metrics.get("shares", 0)

    # 重み付きスコア（いいね・リプライは閲覧数より価値が高い）
    if views == 0:
        return 0.0

    engagement_rate = (likes * 3 + replies * 5 + shares * 4) / max(views, 1) * 100
    reach_score = min(views / 1000, 10)  # 1000閲覧で10点満点
    score = reach_score + engagement_rate

    return round(score, 2)


def analyze_by_pattern(history: list) -> dict:
    """投稿パターン別のパフォーマンス分析"""
    pattern_scores = defaultdict(list)

    for post in history:
        if post.get("metrics") and post.get("pattern_id"):
            score = calculate_post_score(post)
            pattern_scores[post["pattern_id"]].append(score)

    result = {}
    for pattern_id, scores in pattern_scores.items():
        result[pattern_id] = {
            "count": len(scores),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "max_score": round(max(scores), 2) if scores else 0,
            "min_score": round(min(scores), 2) if scores else 0,
        }

    return result


def analyze_by_theme(history: list) -> dict:
    """テーマ別のパフォーマンス分析"""
    theme_scores = defaultdict(list)

    for post in history:
        if post.get("metrics") and post.get("theme"):
            score = calculate_post_score(post)
            theme_scores[post["theme"]].append(score)

    result = {}
    for theme, scores in theme_scores.items():
        result[theme] = {
            "count": len(scores),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else 0,
        }

    return result


def get_top_posts(history: list, n: int = 5) -> list:
    """スコア上位の投稿を取得"""
    scored = [
        {**post, "score": calculate_post_score(post)}
        for post in history
        if post.get("metrics")
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:n]


def get_worst_posts(history: list, n: int = 5) -> list:
    """スコア下位の投稿を取得"""
    scored = [
        {**post, "score": calculate_post_score(post)}
        for post in history
        if post.get("metrics")
    ]
    scored.sort(key=lambda x: x["score"])
    return scored[:n]


def generate_recommendations(pattern_analysis: dict, theme_analysis: dict) -> list:
    """分析結果から推奨事項を生成"""
    recommendations = []

    if not pattern_analysis:
        recommendations.append({
            "type": "info",
            "message": "投稿データが不足しています。まず投稿を蓄積してください。",
        })
        return recommendations

    # トップパターンの推奨
    sorted_patterns = sorted(
        pattern_analysis.items(),
        key=lambda x: x[1]["avg_score"],
        reverse=True,
    )

    if sorted_patterns:
        top_pattern = sorted_patterns[0]
        recommendations.append({
            "type": "use_more",
            "target": "pattern",
            "id": top_pattern[0],
            "reason": f"平均スコア {top_pattern[1]['avg_score']} で最も高パフォーマンス",
        })

    if len(sorted_patterns) > 1:
        worst_pattern = sorted_patterns[-1]
        recommendations.append({
            "type": "avoid",
            "target": "pattern",
            "id": worst_pattern[0],
            "reason": f"平均スコア {worst_pattern[1]['avg_score']} で最も低パフォーマンス",
        })

    # テーマ推奨
    if theme_analysis:
        sorted_themes = sorted(
            theme_analysis.items(),
            key=lambda x: x[1]["avg_score"],
            reverse=True,
        )
        if sorted_themes:
            top_theme = sorted_themes[0]
            recommendations.append({
                "type": "focus_theme",
                "theme": top_theme[0],
                "reason": f"平均スコア {top_theme[1]['avg_score']} で最も反応が良い",
            })

    return recommendations


def run():
    """メイン実行関数"""
    logger.info("=== Analyst Started ===")

    history = load_post_history()
    posts_with_metrics = [p for p in history if p.get("metrics")]

    logger.info(f"Total posts: {len(history)}, With metrics: {len(posts_with_metrics)}")

    # パターン別分析
    pattern_analysis = analyze_by_pattern(history)

    # テーマ別分析
    theme_analysis = analyze_by_theme(history)

    # トップ・ワースト投稿
    top_posts = get_top_posts(history)
    worst_posts = get_worst_posts(history)

    # 全体統計
    total_views = sum(
        p.get("metrics", {}).get("views", 0) for p in posts_with_metrics
    )
    total_likes = sum(
        p.get("metrics", {}).get("likes", 0) for p in posts_with_metrics
    )
    total_replies = sum(
        p.get("metrics", {}).get("replies", 0) for p in posts_with_metrics
    )

    # 推奨事項生成
    recommendations = generate_recommendations(pattern_analysis, theme_analysis)

    # analytics.json更新
    analytics = {
        "last_updated": datetime.now().isoformat(),
        "total_posts": len(history),
        "posts_with_metrics": len(posts_with_metrics),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_replies": total_replies,
        "by_pattern": pattern_analysis,
        "by_theme": theme_analysis,
    }
    save_analytics(analytics)

    # analyst_feedback.json生成（writerへの指示書）
    feedback = {
        "generated_at": datetime.now().isoformat(),
        "recommendations": recommendations,
        "top_performing_patterns": [
            k for k, v in sorted(
                pattern_analysis.items(),
                key=lambda x: x[1]["avg_score"],
                reverse=True,
            )[:3]
        ],
        "underperforming_patterns": [
            k for k, v in sorted(
                pattern_analysis.items(),
                key=lambda x: x[1]["avg_score"],
            )[:2]
        ],
        "top_themes": [
            k for k, v in sorted(
                theme_analysis.items(),
                key=lambda x: x[1]["avg_score"],
                reverse=True,
            )[:3]
        ],
        "top_posts_summary": [
            {
                "id": p.get("id"),
                "theme": p.get("theme"),
                "pattern_id": p.get("pattern_id"),
                "score": p.get("score"),
                "first_line": p.get("content", "")[:50],
            }
            for p in top_posts
        ],
        "avoid_themes": [
            k for k, v in sorted(
                theme_analysis.items(),
                key=lambda x: x[1]["avg_score"],
            )[:2]
        ],
    }
    save_analyst_feedback(feedback)

    logger.info("Analysis complete. Feedback saved.")
    logger.info("=== Analyst Completed ===")
    return feedback


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
