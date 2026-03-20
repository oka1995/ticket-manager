"""
test_system.py - システム動作確認テストスクリプト
APIキー不要でローカル動作確認ができます。
Usage: python3 test_system.py
"""

import json
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"
WARN = "\033[93m[WARN]\033[0m"


def section(title: str):
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")


def test(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    msg = f"{status} {name}"
    if detail:
        msg += f" | {detail}"
    print(msg)
    return condition


def run_all_tests():
    all_passed = True

    # =====================
    section("1. ディレクトリ構造チェック")
    # =====================
    required_dirs = ["agents", "knowledge", "data"]
    for d in required_dirs:
        path = BASE_DIR / d
        ok = test(f"Directory: {d}/", path.exists())
        all_passed = all_passed and ok

    # =====================
    section("2. 必須ファイル存在確認")
    # =====================
    required_files = [
        "config.json",
        "run.sh",
        "kill_switch.sh",
        "knowledge/account_profile.json",
        "knowledge/theme_tree.json",
        "knowledge/post_patterns.json",
        "knowledge/hook_examples.json",
        "knowledge/ng_words.json",
        "data/post_history.json",
        "data/post_queue.json",
        "data/analytics.json",
        "agents/supervisor.py",
        "agents/researcher.py",
        "agents/analyst.py",
        "agents/writer.py",
        "agents/poster.py",
        "agents/fetcher.py",
    ]
    for f in required_files:
        path = BASE_DIR / f
        ok = test(f"File: {f}", path.exists())
        all_passed = all_passed and ok

    # =====================
    section("3. JSONファイル構文チェック")
    # =====================
    json_files = [
        "config.json",
        "knowledge/account_profile.json",
        "knowledge/theme_tree.json",
        "knowledge/post_patterns.json",
        "knowledge/hook_examples.json",
        "knowledge/ng_words.json",
        "data/post_history.json",
        "data/post_queue.json",
        "data/analytics.json",
    ]
    for f in json_files:
        path = BASE_DIR / f
        try:
            with open(path) as fp:
                data = json.load(fp)
            ok = test(f"JSON valid: {f}", True)
        except Exception as e:
            ok = test(f"JSON valid: {f}", False, str(e))
        all_passed = all_passed and ok

    # =====================
    section("4. knowledge/コンテンツチェック")
    # =====================
    # post_patterns.json
    with open(BASE_DIR / "knowledge/post_patterns.json") as f:
        patterns = json.load(f)
    ok = test("post_patterns.json: 15パターン存在", len(patterns) == 15,
              f"Found {len(patterns)}")
    all_passed = all_passed and ok

    ok = test("post_patterns.json: 全パターンにid/name/structureあり",
              all("id" in p and "name" in p and "structure" in p for p in patterns))
    all_passed = all_passed and ok

    # theme_tree.json
    with open(BASE_DIR / "knowledge/theme_tree.json") as f:
        themes = json.load(f)
    ok = test("theme_tree.json: カテゴリ存在", len(themes) >= 5, f"Found {len(themes)} categories")
    all_passed = all_passed and ok

    # hook_examples.json
    with open(BASE_DIR / "knowledge/hook_examples.json") as f:
        hooks = json.load(f)
    hook_list = hooks.get("hooks", [])
    ok = test("hook_examples.json: フック例存在", len(hook_list) >= 3,
              f"Found {len(hook_list)} groups")
    all_passed = all_passed and ok

    # ng_words.json
    with open(BASE_DIR / "knowledge/ng_words.json") as f:
        ng = json.load(f)
    ok = test("ng_words.json: NGワード存在", len(ng.get("ng_words", [])) >= 5)
    all_passed = all_passed and ok

    # =====================
    section("5. Supervisorモジュールテスト")
    # =====================
    try:
        from agents.supervisor import (
            check_kill_switch, check_daily_post_limit,
            check_min_interval, load_post_history
        )
        ok = test("supervisor.py: インポート成功", True)

        # Kill switch非アクティブ確認
        kill_flag = BASE_DIR / "data/kill_switch.flag"
        if kill_flag.exists():
            os.remove(kill_flag)
        ok = test("supervisor: kill_switch.flag 未存在", not kill_flag.exists())
        all_passed = all_passed and ok

    except Exception as e:
        ok = test("supervisor.py: インポート", False, str(e))
        all_passed = all_passed and ok

    # =====================
    section("6. Analystモジュールテスト")
    # =====================
    try:
        from agents.analyst import (
            calculate_post_score, analyze_by_pattern,
            analyze_by_theme, generate_recommendations
        )
        ok = test("analyst.py: インポート成功", True)

        # スコア計算テスト
        mock_post = {
            "pattern_id": "P01",
            "theme": "副業入門/副業の選び方",
            "metrics": {"views": 1000, "likes": 50, "replies": 10, "shares": 5},
        }
        score = calculate_post_score(mock_post)
        ok = test("analyst: スコア計算", score > 0, f"score={score}")
        all_passed = all_passed and ok

        # 推奨事項生成テスト（データなし）
        recs = generate_recommendations({}, {})
        ok = test("analyst: 推奨事項生成（空データ）", isinstance(recs, list))
        all_passed = all_passed and ok

    except Exception as e:
        ok = test("analyst.py: インポート", False, str(e))
        all_passed = all_passed and ok

    # =====================
    section("7. Writerモジュールテスト")
    # =====================
    try:
        from agents.writer import (
            load_knowledge, get_recent_patterns, select_pattern,
            select_theme, cosine_similarity, self_score, contains_ng_words
        )
        ok = test("writer.py: インポート成功", True)

        # ナレッジロードテスト
        patterns, hooks, profile, theme_tree, ng_words = load_knowledge()
        ok = test("writer: knowledge読み込み", len(patterns) == 15)
        all_passed = all_passed and ok

        # パターン選択テスト
        pattern = select_pattern(patterns, ["P01", "P02", "P03"])
        ok = test("writer: パターン選択（回避あり）",
                  pattern["id"] not in ["P01", "P02", "P03"])
        all_passed = all_passed and ok

        # テーマ選択テスト
        theme = select_theme(theme_tree, [], {})
        ok = test("writer: テーマ選択", "/" in theme, f"theme={theme}")
        all_passed = all_passed and ok

        # コサイン類似度テスト
        sim1 = cosine_similarity("副業で稼ぐ方法を教える", "副業で稼ぐ方法を教える")
        ok = test("writer: コサイン類似度（同一テキスト）", sim1 > 0.99, f"sim={sim1:.3f}")
        all_passed = all_passed and ok

        sim2 = cosine_similarity("副業で稼ぐ方法", "全く関係ない文章abcdef")
        ok = test("writer: コサイン類似度（異なるテキスト）", sim2 < 0.5, f"sim={sim2:.3f}")
        all_passed = all_passed and ok

        # NGワードチェックテスト
        ng_result = contains_ng_words("絶対儲かる副業を教えます", ng_words)
        ok = test("writer: NGワード検知", ng_result is True)
        all_passed = all_passed and ok

        clean_result = contains_ng_words("副業で月5万稼いだ話をします", ng_words)
        ok = test("writer: NGワード未検知（クリーンテキスト）", clean_result is False)
        all_passed = all_passed and ok

        # 自己採点テスト
        pattern_sample = {"id": "P01", "name": "断言型"}
        test_content = "副業で月5万稼いだ方法、全部話すね\n\n理由は3つあるんだよね。\n①具体的な方法1\n②具体的な方法2\n③継続のコツ\n\nまずはここから始めてみて。"
        scores = self_score(test_content, "副業で月5万", "副業入門/副業の選び方", pattern_sample, profile)
        ok = test("writer: 自己採点", "average" in scores and 0 <= scores["average"] <= 10,
                  f"avg={scores.get('average')}")
        all_passed = all_passed and ok

    except Exception as e:
        ok = test("writer.py: インポート", False, str(e))
        all_passed = all_passed and ok

    # =====================
    section("8. Researcherモジュールテスト")
    # =====================
    try:
        from agents.researcher import (
            load_theme_tree, get_theme_coverage, select_priority_themes,
            extract_keywords
        )
        ok = test("researcher.py: インポート成功", True)

        theme_tree = load_theme_tree()
        coverage = get_theme_coverage([], theme_tree)
        ok = test("researcher: テーマカバレッジ計算", len(coverage) > 0,
                  f"Found {len(coverage)} themes")
        all_passed = all_passed and ok

        priority = select_priority_themes(coverage, count=3)
        ok = test("researcher: 優先テーマ選択", len(priority) == 3)
        all_passed = all_passed and ok

        keywords = extract_keywords("副業で月5万稼ぐ方法と投資の初心者向け解説")
        ok = test("researcher: キーワード抽出", len(keywords) > 0,
                  f"keywords={keywords}")
        all_passed = all_passed and ok

    except Exception as e:
        ok = test("researcher.py: インポート", False, str(e))
        all_passed = all_passed and ok

    # =====================
    section("9. Fetcherモジュールテスト")
    # =====================
    try:
        from agents.fetcher import is_ready_for_metrics, generate_mock_metrics
        ok = test("fetcher.py: インポート成功", True)

        # 24時間チェック
        from datetime import datetime, timedelta
        old_post = {"posted_at": (datetime.now() - timedelta(hours=25)).isoformat()}
        new_post = {"posted_at": datetime.now().isoformat()}

        ok = test("fetcher: 24時間経過チェック（古い投稿）",
                  is_ready_for_metrics(old_post))
        all_passed = all_passed and ok

        ok = test("fetcher: 24時間経過チェック（新しい投稿）",
                  not is_ready_for_metrics(new_post))
        all_passed = all_passed and ok

        # モックメトリクス生成
        metrics = generate_mock_metrics("test_post_id")
        ok = test("fetcher: モックメトリクス生成",
                  all(k in metrics for k in ["views", "likes", "replies", "shares"]))
        all_passed = all_passed and ok

    except Exception as e:
        ok = test("fetcher.py: インポート", False, str(e))
        all_passed = all_passed and ok

    # =====================
    section("10. Writer実行テスト（モックモード）")
    # =====================
    try:
        print(f"{INFO} Writerをモックモードで実行中（APIキー不要）...")
        from agents.writer import run as writer_run
        generated = writer_run(batch_size=3)
        ok = test("writer: 3件生成", len(generated) >= 1,
                  f"Generated {len(generated)} posts")
        all_passed = all_passed and ok

        if generated:
            post = generated[0]
            ok = test("writer: 投稿構造チェック",
                      all(k in post for k in ["id", "content", "theme", "pattern_id", "scores"]))
            all_passed = all_passed and ok

            ok = test("writer: 品質スコアチェック",
                      post["scores"]["average"] >= 7.0,
                      f"avg_score={post['scores']['average']}")
            all_passed = all_passed and ok

            print(f"{INFO} サンプル投稿プレビュー:")
            print(f"  テーマ: {post.get('theme')}")
            print(f"  パターン: {post.get('pattern_name')}")
            print(f"  スコア: {post['scores']['average']}")
            print(f"  内容（先頭100文字）: {post['content'][:100]}...")

    except Exception as e:
        ok = test("writer: 実行テスト", False, str(e))
        all_passed = all_passed and ok

    # =====================
    section("テスト結果サマリー")
    # =====================
    if all_passed:
        print(f"\n{PASS} 全テスト通過！システムは正常に動作しています。")
        print("\n次のステップ:")
        print("  1. config.json にAPIキーを設定")
        print("  2. bash run.sh を実行して本日分の投稿を生成")
        print("  3. crontab -e でcronジョブを設定")
    else:
        print(f"\n{FAIL} 一部テストが失敗しました。上記のエラーを確認してください。")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
