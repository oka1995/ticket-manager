"""
writer.py - 投稿生成エージェント
- hook_examples.jsonを参照して1行目を生成
- post_patterns.jsonから直近3件と異なるパターンを選択
- 同じテーマが3連続したら自動で別テーマに切り替え
- 生成後に自己採点（平均7.0以上のみキューに追加）
- 過去100件とのコサイン類似度チェック（0.85以上は棄却）
- アフィリエイト投稿は全体の20%程度に抑える
- 1回のバッチで5〜10本生成
"""

import json
import sys
import math
import logging
import random
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
POST_HISTORY_FILE = DATA_DIR / "post_history.json"
POST_QUEUE_FILE = DATA_DIR / "post_queue.json"
RESEARCH_POOL_FILE = DATA_DIR / "research_pool.json"
ANALYST_FEEDBACK_FILE = DATA_DIR / "analyst_feedback.json"
SUPERVISOR_LOG_FILE = DATA_DIR / "supervisor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WRITER] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(SUPERVISOR_LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


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


def load_knowledge():
    patterns = load_json(KNOWLEDGE_DIR / "post_patterns.json")
    hooks = load_json(KNOWLEDGE_DIR / "hook_examples.json")
    profile = load_json(KNOWLEDGE_DIR / "account_profile.json")
    theme_tree = load_json(KNOWLEDGE_DIR / "theme_tree.json")
    ng_words = load_json(KNOWLEDGE_DIR / "ng_words.json")
    return patterns, hooks, profile, theme_tree, ng_words


def get_recent_patterns(history: list, n: int = 3) -> list:
    """直近n件の投稿パターンIDを返す"""
    recent = sorted(history, key=lambda x: x.get("created_at", ""), reverse=True)[:n]
    return [p.get("pattern_id") for p in recent if p.get("pattern_id")]


def get_recent_themes(history: list, n: int = 3) -> list:
    """直近n件の投稿テーマを返す"""
    recent = sorted(history, key=lambda x: x.get("created_at", ""), reverse=True)[:n]
    return [p.get("theme") for p in recent if p.get("theme")]


def select_pattern(patterns: list, avoid_patterns: list) -> dict:
    """直近と異なるパターンを選択"""
    available = [p for p in patterns if p["id"] not in avoid_patterns]
    if not available:
        available = patterns
    return random.choice(available)


def select_theme(theme_tree: dict, avoid_themes: list, feedback: dict) -> str:
    """テーマを選択（3連続同一テーマを避ける）"""
    all_themes = []
    for category, sub_themes in theme_tree.items():
        for sub in sub_themes:
            all_themes.append(f"{category}/{sub}")

    # フィードバックのトップテーマを優先
    top_themes = feedback.get("top_themes", []) if feedback else []
    avoid = avoid_themes if avoid_themes else []

    # 直近3件が同じテーマなら別テーマを選択
    if len(set(avoid)) == 1 and len(avoid) >= 3:
        available = [t for t in all_themes if t != avoid[0]]
    else:
        available = all_themes

    # トップテーマがあれば優先
    prioritized = [t for t in top_themes if t in available]
    if prioritized:
        return random.choice(prioritized)

    return random.choice(available) if available else random.choice(all_themes)


def get_hook_example(hooks_data: dict, pattern_name: str) -> str:
    """フック例を取得"""
    hooks_list = hooks_data.get("hooks", [])

    # パターン名に合うフックを探す
    for hook_group in hooks_list:
        if any(keyword in pattern_name for keyword in
               hook_group.get("pattern", "").split("・")):
            examples = hook_group.get("examples", [])
            if examples:
                return random.choice(examples)

    # 見つからない場合はランダム
    all_examples = []
    for group in hooks_list:
        all_examples.extend(group.get("examples", []))
    return random.choice(all_examples) if all_examples else "副業で月5万稼いだ方法を話すね"


def contains_ng_words(text: str, ng_words_data: dict) -> bool:
    """NGワードが含まれているか確認"""
    ng_list = ng_words_data.get("ng_words", [])
    return any(word in text for word in ng_list)


def tokenize(text: str) -> list:
    """簡易トークナイズ（文字n-gram）"""
    text = text.replace("\n", " ").replace("　", " ")
    bigrams = [text[i:i+2] for i in range(len(text) - 1)]
    return bigrams


def cosine_similarity(text1: str, text2: str) -> float:
    """コサイン類似度の計算"""
    tokens1 = Counter(tokenize(text1))
    tokens2 = Counter(tokenize(text2))

    all_tokens = set(tokens1.keys()) | set(tokens2.keys())
    if not all_tokens:
        return 0.0

    dot_product = sum(tokens1.get(t, 0) * tokens2.get(t, 0) for t in all_tokens)
    norm1 = math.sqrt(sum(v**2 for v in tokens1.values()))
    norm2 = math.sqrt(sum(v**2 for v in tokens2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def is_too_similar(new_content: str, history: list, threshold: float = 0.85) -> bool:
    """過去100件の投稿と類似度チェック"""
    recent_100 = sorted(
        history, key=lambda x: x.get("created_at", ""), reverse=True
    )[:100]

    for post in recent_100:
        content = post.get("content", "")
        if content and cosine_similarity(new_content, content) >= threshold:
            return True
    return False


def self_score(content: str, hook: str, theme: str, pattern: dict, profile: dict) -> dict:
    """投稿の自己採点（各項目10点満点）"""
    scores = {}

    # フック強度（1行目のインパクト）
    first_line = content.split("\n")[0] if "\n" in content else content[:50]
    hook_score = 5.0
    if any(c.isdigit() for c in first_line):
        hook_score += 2.0  # 数字あり
    if "？" in first_line or "?" in first_line:
        hook_score += 1.0  # 問いかけ
    if any(word in first_line for word in ["やめて", "絶対", "正直", "暴露", "告白"]):
        hook_score += 2.0  # インパクトワード
    scores["hook"] = min(hook_score, 10.0)

    # 有益性
    useful_score = 5.0
    useful_keywords = ["方法", "コツ", "ポイント", "理由", "原因", "対策", "ステップ"]
    found = sum(1 for kw in useful_keywords if kw in content)
    useful_score += min(found * 1.5, 4.0)
    scores["usefulness"] = min(useful_score, 10.0)

    # 具体性
    specific_score = 5.0
    if any(c.isdigit() for c in content):
        specific_score += 2.0
    if "万円" in content or "万" in content:
        specific_score += 1.0
    if "%" in content:
        specific_score += 1.0
    scores["specificity"] = min(specific_score, 10.0)

    # テンポ（改行・箇条書き）
    lines = content.split("\n")
    tempo_score = 5.0
    if len(lines) >= 3:
        tempo_score += 2.0
    if any("・" in l or "→" in l or "▼" in l for l in lines):
        tempo_score += 2.0
    scores["tempo"] = min(tempo_score, 10.0)

    # ペルソナ一致度
    persona_score = 5.0
    persona_words = ["だよ", "なんだよね", "んだよね", "よね", "じゃん", "かな"]
    found_persona = sum(1 for w in persona_words if w in content)
    persona_score += min(found_persona * 1.5, 4.0)
    scores["persona"] = min(persona_score, 10.0)

    average = sum(scores.values()) / len(scores)
    scores["average"] = round(average, 2)
    return scores


def generate_post_with_claude(
    theme: str,
    pattern: dict,
    hook_example: str,
    profile: dict,
    research_idea: Optional[dict],
    feedback: dict,
) -> str:
    """Claude APIを使って投稿を生成"""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic module not installed. Using template generation.")
        return generate_post_template(theme, pattern, hook_example, profile)

    config = load_config()
    api_key = config["claude_api"]["api_key"]

    if api_key.startswith("【"):
        return generate_post_template(theme, pattern, hook_example, profile)

    client = anthropic.Anthropic(api_key=api_key)

    research_context = ""
    if research_idea:
        research_context = f"""
参考ネタ（YouTubeから収集）:
タイトル: {research_idea.get('title', '')}
説明: {research_idea.get('description', '')[:200]}
"""

    prompt = f"""あなたは副業で月5万〜30万を実現した30代会社員として、Threadsに投稿するテキストを生成してください。

## アカウントペルソナ
{profile.get('persona', '')}

## 口調
{profile.get('tone', '')}

## 今回のテーマ
{theme}

## 投稿パターン
{pattern['name']}: {pattern['structure']}

## 1行目の参考フック
{hook_example}

{research_context}

## 制約
- 文字数: 150〜500文字
- 1行目は必ずインパクトのある一文で始める
- 友達に話すような口調で（「だよ」「なんだよね」などを使う）
- 上から目線NG
- 具体的な数字を入れる
- 改行を効果的に使ってテンポよく
- NGワード厳禁: 絶対儲かる、誰でも稼げる、楽して稼ぐ、不労所得

## 出力
投稿テキストのみを出力してください。説明不要。"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return generate_post_template(theme, pattern, hook_example, profile)


def generate_post_template(
    theme: str, pattern: dict, hook_example: str, profile: dict
) -> str:
    """テンプレートベースの投稿生成（APIキー未設定時のフォールバック）"""
    theme_name = theme.split("/")[-1] if "/" in theme else theme
    templates = {
        "断言型": f"{hook_example}\n\n理由は3つあるんだよね。\n\n①具体的な理由1\n②具体的な理由2\n③具体的な理由3\n\n{theme_name}で悩んでる人は、まずここから始めてみて。",
        "暴露型": f"{hook_example}\n\n実は自分も騙されかけた経験があって...\n\n詳しく話すと、{theme_name}には落とし穴があるんだよね。\n\n同じ失敗をしてほしくないから、正直に全部話す。",
        "リスト型": f"{theme_name}でやるべきこと5選\n\n①まず○○から始める\n②次に△△を確認する\n③□□を設定する\n④★★を実行する\n⑤継続する仕組みを作る\n\nこの順番が大事なんだよね。",
        "共感型": f"{theme_name}で悩んでる人いる？\n\n正直、最初は自分も全然分からなかった。\n\nでも、たった1つのことを変えたら月5万稼げるようになったんだよね。\n\nその方法、気になる人はコメントして。",
        "失敗談型": f"正直に話す。{theme_name}で大失敗した。\n\n原因は○○だったんだよね。\n\nあの時の自分に伝えるとしたら、「まず△△しろ」って言う。\n\n同じ失敗しないでね。",
    }

    content = templates.get(
        pattern["name"],
        f"{hook_example}\n\n{theme_name}について、自分の経験をもとに話すね。\n\n副業3ヶ月で月5万達成した方法を、ステップ別に解説するよ。\n\n気になった人はコメントして！",
    )
    return content


def run(batch_size: int = 7):
    """メイン実行関数"""
    logger.info("=== Writer Started ===")

    config = load_config()
    quality_threshold = config["settings"]["quality_threshold"]
    similarity_threshold = config["settings"]["similarity_threshold"]

    patterns, hooks, profile, theme_tree, ng_words = load_knowledge()
    history = load_json(POST_HISTORY_FILE)
    queue = load_json(POST_QUEUE_FILE)
    research_pool = load_json(RESEARCH_POOL_FILE)
    feedback = load_json(ANALYST_FEEDBACK_FILE) if ANALYST_FEEDBACK_FILE.exists() else {}

    recent_patterns = get_recent_patterns(history)
    recent_themes = get_recent_themes(history)

    # アフィリエイト投稿の割合チェック（全体の20%以内）
    total_in_queue = len(queue)
    affiliate_count = sum(1 for p in queue if p.get("is_affiliate"))
    max_affiliate = max(1, int(total_in_queue * 0.2))

    generated = []
    rejected = []

    unused_research = [r for r in research_pool if not r.get("used")]

    for i in range(batch_size * 3):  # 棄却を考慮して多めに試行
        if len(generated) >= batch_size:
            break

        # パターン・テーマ選択
        pattern = select_pattern(patterns, recent_patterns[-3:] if recent_patterns else [])
        theme = select_theme(theme_tree, recent_themes[-3:] if recent_themes else [], feedback)

        # アフィリエイト判定
        is_affiliate = (pattern["id"] == "P15") and (affiliate_count < max_affiliate)
        if pattern["id"] == "P15" and affiliate_count >= max_affiliate:
            pattern = select_pattern(patterns, recent_patterns[-3:] + ["P15"])

        # リサーチデータから関連ネタを取得
        research_idea = None
        if unused_research:
            relevant = [r for r in unused_research if theme.split("/")[-1] in r.get("title", "")]
            research_idea = relevant[0] if relevant else unused_research[0] if unused_research else None

        # フック例取得
        hook = get_hook_example(hooks, pattern["name"])

        # 投稿生成
        content = generate_post_with_claude(theme, pattern, hook, profile, research_idea, feedback)

        # NGワードチェック
        if contains_ng_words(content, ng_words):
            logger.warning(f"Post rejected: contains NG words. Theme: {theme}")
            rejected.append({"reason": "ng_words", "theme": theme})
            continue

        # 類似度チェック
        if is_too_similar(content, history, similarity_threshold):
            logger.warning(f"Post rejected: too similar to existing posts. Theme: {theme}")
            rejected.append({"reason": "too_similar", "theme": theme})
            continue

        # 自己採点
        scores = self_score(content, hook, theme, pattern, profile)
        avg = scores["average"]

        if avg < quality_threshold:
            # 再生成（最大2回）
            retry_success = False
            for retry in range(2):
                content = generate_post_with_claude(theme, pattern, hook, profile, research_idea, feedback)
                if contains_ng_words(content, ng_words):
                    continue
                if is_too_similar(content, history, similarity_threshold):
                    continue
                scores = self_score(content, hook, theme, pattern, profile)
                if scores["average"] >= quality_threshold:
                    retry_success = True
                    break

            if not retry_success:
                logger.warning(f"Post rejected after 2 retries. Score: {scores['average']}")
                rejected.append({"reason": "low_quality", "score": scores["average"], "theme": theme})
                continue

        # キューに追加
        post = {
            "id": f"P{datetime.now().strftime('%Y%m%d%H%M%S')}_{i:02d}",
            "content": content,
            "theme": theme,
            "pattern_id": pattern["id"],
            "pattern_name": pattern["name"],
            "is_affiliate": is_affiliate,
            "scores": scores,
            "created_at": datetime.now().isoformat(),
            "scheduled_at": None,
            "status": "queued",
        }
        generated.append(post)

        if is_affiliate:
            affiliate_count += 1

        recent_patterns.append(pattern["id"])
        recent_themes.append(theme)

        # リサーチアイテムを使用済みにマーク
        if research_idea:
            for r in research_pool:
                if r.get("id") == research_idea.get("id"):
                    r["used"] = True

    # キューに追加
    queue.extend(generated)
    save_json(POST_QUEUE_FILE, queue)

    # リサーチプールを更新
    if research_pool:
        save_json(RESEARCH_POOL_FILE, research_pool)

    logger.info(
        f"Generated: {len(generated)}, Rejected: {len(rejected)}. "
        f"Queue size: {len(queue)}"
    )
    logger.info("=== Writer Completed ===")
    return generated


if __name__ == "__main__":
    result = run()
    print(f"Generated {len(result)} posts.")
    for post in result:
        print(f"\n--- {post['pattern_name']} | {post['theme']} | Score: {post['scores']['average']} ---")
        print(post["content"][:100] + "..." if len(post["content"]) > 100 else post["content"])
