# -*- coding: utf-8 -*-
"""
SNS熱量から「いま投稿するなら熱い商品」を選び、紹介文を作るツール。

標準ライブラリだけで動きます。APIキーが無いSNSは自動でスキップします。

使い方:
  python sns_hot_copy.py --offline --dry-run
  python sns_hot_copy.py --sources bluesky,reddit,x,youtube,manual

対応ソース:
  X        : X_BEARER_TOKEN があれば recent counts を使う
  YouTube  : YOUTUBE_API_KEY があれば直近動画検索を使う
  Bluesky  : 公開検索APIを使う
  Reddit   : 公開JSON検索を使う
  manual   : SNS_SIGNAL_FILE または --signal-file で手動CSV/JSONを足せる

手動ファイル例(JSON):
  [{"term": "ポケカ", "source": "TikTok", "count": 18}]
  {"ポケカ": {"Instagram": 12, "Threads": 6}}

手動ファイル例(CSV):
  term,source,count
  ポケカ,TikTok,18
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "docs" / "data.json"
RULES_PATH = HERE / "docs" / "hashtag-rules.json"
DEFAULT_JSON_OUT = HERE / "docs" / "sns-hot-copy.json"
DEFAULT_TEXT_OUT = HERE / "docs" / "sns-hot-post.txt"
JST = timezone(timedelta(hours=9))

SOURCE_WEIGHTS = {
    "x": 1.8,
    "bluesky": 1.2,
    "reddit": 0.9,
    "youtube": 1.1,
    "manual": 1.4,
}

CATEGORY_COPY = {
    "ポケモンカード": {
        "short": "ポケカ",
        "focus": "BOXや拡張パック",
        "watch": "在庫や価格差",
        "tags": ["#ポケカ", "#ポケモンカード"],
    },
    "ワンピースカード": {
        "short": "ワンピカード",
        "focus": "BOXやブースターパック",
        "watch": "再販や予約枠",
        "tags": ["#ワンピースカード"],
    },
    "遊戯王・他カード": {
        "short": "TCG",
        "focus": "BOXやブースターパック",
        "watch": "予約枠や価格",
        "tags": ["#遊戯王", "#TCG"],
    },
    "フィギュア": {
        "short": "フィギュア",
        "focus": "スケールフィギュアや完成品",
        "watch": "予約締切や価格",
        "tags": ["#フィギュア"],
    },
    "ねんどろいど・figma": {
        "short": "ねんどろいど・figma",
        "focus": "可動・デフォルメ系",
        "watch": "再販や特典",
        "tags": ["#ねんどろいど", "#figma"],
    },
    "ガンプラ・プラモデル": {
        "short": "ガンプラ・プラモ",
        "focus": "新作や再販キット",
        "watch": "再販枠や在庫",
        "tags": ["#ガンプラ", "#プラモデル"],
    },
    "ゲームソフト": {
        "short": "ゲーム予約",
        "focus": "新作ソフトや特典付き",
        "watch": "店舗特典や在庫",
        "tags": ["#ゲーム"],
    },
    "アニメBlu-ray・CD": {
        "short": "アニメBD/CD",
        "focus": "初回特典や限定版",
        "watch": "予約特典や締切",
        "tags": ["#アニメ", "#Blu_ray"],
    },
    "特撮・なりきり玩具": {
        "short": "特撮玩具",
        "focus": "変身アイテムや関連玩具",
        "watch": "発売直後の在庫",
        "tags": ["#特撮", "#仮面ライダー"],
    },
    "鉄道模型": {
        "short": "鉄道模型",
        "focus": "Nゲージや車両セット",
        "watch": "再生産や予約枠",
        "tags": ["#鉄道模型"],
    },
    "トミカ・ミニカー": {
        "short": "トミカ・ミニカー",
        "focus": "初回特別仕様や新車",
        "watch": "初回仕様や在庫",
        "tags": ["#トミカ", "#ミニカー"],
    },
    "ぬいぐるみ・グッズ": {
        "short": "キャラグッズ",
        "focus": "ぬいぐるみやアクスタ",
        "watch": "予約枠や再入荷",
        "tags": ["#グッズ", "#ぬいぐるみ"],
    },
}

STOPWORDS = {
    "予約", "予約商品", "送料無料", "特典", "付き", "セット", "限定", "通常版",
    "新品", "未開封", "国内正規品", "発売", "発送", "入荷", "予定", "販売",
    "ポイント", "クーポン", "レビュー", "ランキング", "セール", "あす楽",
    "BOX", "ボックス", "パック", "カートン", "グッズ", "カード", "ゲーム",
    "フィギュア", "プラモデル", "ぬいぐるみ", "ソフト", "楽天", "市場",
}


def log(message: str) -> None:
    print(message, file=sys.stderr)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", clean_text(value))


def core_name(name: str, limit: int = 82) -> str:
    text = normalize(name)
    text = re.sub(r"【[^】]*】|\[[^\]]*\]|\([^)]*\)", " ", text)
    text = re.sub(
        r"(送料無料|予約商品|予約|発売予定|発売|特典付き|レビュー特典|ポイントバック|"
        r"期間限定|国内正規品|新品未開封|新品|未開封|シュリンク付き)",
        " ",
        text,
    )
    text = clean_text(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def tokenize(text: str) -> list[str]:
    text = normalize(text)
    tokens = re.findall(r"[ァ-ヶー]{3,}|[一-龥々]{2,}|[A-Za-z][A-Za-z0-9.+\-]{2,}", text)
    out: list[str] = []
    for token in tokens:
        token = token.strip("ー-.")
        if not token or token in STOPWORDS or token.upper() in STOPWORDS:
            continue
        if re.fullmatch(r"\d+", token):
            continue
        out.append(token)
    return out


def load_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for genre in data.get("genres", []):
        for item in genre.get("items", []):
            if not item.get("url") or not item.get("name"):
                continue
            rows.append({"genre": genre, "item": item})
    return rows


def base_score(row: dict[str, Any]) -> float:
    item = row["item"]
    score = 0.0
    if item.get("is_new"):
        score += 28
    if item.get("hot"):
        score += 18
    if item.get("image"):
        score += 4
    if item.get("release"):
        score += 3
    price = int(item.get("price") or 0)
    if 1500 <= price <= 25000:
        score += 3
    return score


def terms_for_row(row: dict[str, Any], title_keywords: list[str]) -> list[str]:
    name = normalize(row["item"].get("name", ""))
    genre_name = normalize(row["genre"].get("name", ""))
    terms: list[str] = []
    for keyword in sorted(title_keywords, key=len, reverse=True):
        if 3 <= len(keyword) <= 28 and keyword in name:
            terms.append(keyword)
        if len(terms) >= 2:
            break
    for token in tokenize(name):
        if token not in terms:
            terms.append(token)
        if len(terms) >= 3:
            break
    if not terms:
        terms.append(CATEGORY_COPY.get(genre_name, {}).get("short", genre_name))
    return terms[:3]


def request_json(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "sns-hot-copy/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8", errors="replace"))


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(JST)
    except Exception:
        return None


def x_count(term: str, hours: int) -> int:
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        return 0
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    query = f'"{term}" lang:ja -is:retweet'
    params = urllib.parse.urlencode({"query": query, "start_time": since})
    url = f"https://api.twitter.com/2/tweets/counts/recent?{params}"
    data = request_json(url, {"Authorization": f"Bearer {token}", "User-Agent": "sns-hot-copy/1.0"})
    return int(data.get("meta", {}).get("total_tweet_count") or 0)


def bluesky_count(term: str, hours: int) -> int:
    cutoff = datetime.now(JST) - timedelta(hours=hours)
    params = urllib.parse.urlencode({"q": term, "limit": 50, "sort": "latest"})
    url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?{params}"
    data = request_json(url)
    count = 0
    for post in data.get("posts", []):
        indexed = parse_dt(post.get("indexedAt"))
        if indexed is None or indexed >= cutoff:
            count += 1
    return count


def reddit_count(term: str, hours: int) -> int:
    cutoff = datetime.now(JST) - timedelta(hours=hours)
    params = urllib.parse.urlencode({"q": term, "sort": "new", "t": "day", "limit": 25})
    url = f"https://www.reddit.com/search.json?{params}"
    data = request_json(url, {"User-Agent": "sns-hot-copy/1.0 by imaure"})
    count = 0
    for child in data.get("data", {}).get("children", []):
        created = child.get("data", {}).get("created_utc")
        if not created:
            count += 1
            continue
        if datetime.fromtimestamp(float(created), tz=timezone.utc).astimezone(JST) >= cutoff:
            count += 1
    return count


def youtube_count(term: str, hours: int) -> int:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return 0
    published_after = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    params = urllib.parse.urlencode({
        "part": "snippet",
        "type": "video",
        "order": "date",
        "maxResults": 10,
        "q": term,
        "publishedAfter": published_after,
        "key": key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    data = request_json(url)
    return len(data.get("items", []))


def load_manual_signals(path: Path | None) -> dict[str, dict[str, int]]:
    if path is None or not path.exists():
        return {}
    out: dict[str, dict[str, int]] = defaultdict(dict)
    if path.suffix.lower() == ".json":
        data = read_json(path, [])
        if isinstance(data, dict):
            for term, sources in data.items():
                if isinstance(sources, dict):
                    for source, value in sources.items():
                        out[clean_text(term)][clean_text(source)] = int(float(value or 0))
        elif isinstance(data, list):
            for row in data:
                term = clean_text(row.get("term"))
                source = clean_text(row.get("source") or "manual")
                value = row.get("count", row.get("score", 0))
                if term:
                    out[term][source] = int(float(value or 0))
        return dict(out)

    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            term = clean_text(row.get("term"))
            source = clean_text(row.get("source") or "manual")
            value = row.get("count") or row.get("score") or 0
            if term:
                out[term][source] = int(float(value or 0))
    return dict(out)


def manual_count(term: str, manual: dict[str, dict[str, int]]) -> tuple[int, dict[str, int]]:
    matched: dict[str, int] = {}
    norm = normalize(term).lower()
    for key, sources in manual.items():
        k = normalize(key).lower()
        if k and (k in norm or norm in k):
            for source, value in sources.items():
                matched[source] = matched.get(source, 0) + int(value)
    return sum(matched.values()), matched


def collect_signals(terms: list[str], args: argparse.Namespace) -> dict[str, dict[str, int]]:
    sources = {s.strip().lower() for s in args.sources.split(",") if s.strip()}
    if args.offline:
        sources = {"manual"}
    signal_file = args.signal_file or os.environ.get("SNS_SIGNAL_FILE", "")
    manual = load_manual_signals(Path(signal_file) if signal_file else None)
    signals: dict[str, dict[str, int]] = {term: {} for term in terms}

    if "x" in sources and not os.environ.get("X_BEARER_TOKEN", "").strip():
        log("[SNS] X_BEARER_TOKEN 未設定のためX検索はスキップ")
    if "youtube" in sources and not os.environ.get("YOUTUBE_API_KEY", "").strip():
        log("[SNS] YOUTUBE_API_KEY 未設定のためYouTube検索はスキップ")

    for i, term in enumerate(terms, 1):
        if "manual" in sources:
            total, detail = manual_count(term, manual)
            if total:
                signals[term]["manual"] = total
                for source, value in detail.items():
                    signals[term][source] = value
        if "x" in sources and os.environ.get("X_BEARER_TOKEN", "").strip():
            try:
                signals[term]["x"] = x_count(term, args.hours)
            except Exception as e:
                log(f"[SNS] X検索失敗({term}): {e}")
        if "bluesky" in sources:
            try:
                signals[term]["bluesky"] = bluesky_count(term, args.hours)
            except Exception as e:
                log(f"[SNS] Bluesky検索失敗({term}): {e}")
        if "reddit" in sources:
            try:
                signals[term]["reddit"] = reddit_count(term, args.hours)
            except Exception as e:
                log(f"[SNS] Reddit検索失敗({term}): {e}")
        if "youtube" in sources and os.environ.get("YOUTUBE_API_KEY", "").strip():
            try:
                signals[term]["youtube"] = youtube_count(term, args.hours)
            except Exception as e:
                log(f"[SNS] YouTube検索失敗({term}): {e}")
        if args.delay and i < len(terms):
            time.sleep(args.delay)
    return signals


def score_from_signals(term_signals: dict[str, int]) -> float:
    score = 0.0
    for source, count in term_signals.items():
        key = source.lower()
        weight = SOURCE_WEIGHTS.get(key, SOURCE_WEIGHTS["manual"])
        score += math.log1p(max(0, int(count))) * 8 * weight
    return score


def tags_for(row: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    tags = []
    genre = row["genre"]
    name = clean_text(genre.get("name"))
    tags.extend(CATEGORY_COPY.get(name, {}).get("tags", []))
    if genre.get("tag"):
        tags.append(genre["tag"])
    tags.extend(rules.get("default_tags", ["#予約開始レーダー", "#ホビー予約"]))
    unique = []
    for tag in tags:
        if tag and tag.startswith("#") and tag not in unique:
            unique.append(tag)
    return unique[:4]


def signal_label(signals: dict[str, int]) -> str:
    items = [(source, count) for source, count in signals.items() if count > 0]
    items.sort(key=lambda x: x[1], reverse=True)
    if not items:
        return "新着度・カテゴリ注目度から選出"
    return " / ".join(f"{source}:{count}" for source, count in items[:4])


def build_intro(row: dict[str, Any], signals: dict[str, int], rules: dict[str, Any]) -> str:
    genre_name = clean_text(row["genre"].get("name"))
    item = row["item"]
    meta = CATEGORY_COPY.get(genre_name, {})
    short = meta.get("short", genre_name)
    focus = meta.get("focus", "予約商品")
    watch = meta.get("watch", "在庫や価格の動き")
    name = core_name(item.get("name", ""))
    price = f"{int(item.get('price') or 0):,}円" if item.get("price") else "価格確認"
    tags = " ".join(tags_for(row, rules))
    return "\n".join([
        f"{short}でSNS反応を見ながら拾った予約候補です。",
        f"{focus}を追っている人は、{watch}が動く前に確認しておくとよさそうです。",
        "",
        name,
        f"{price} / {clean_text(item.get('shop'))}",
        signal_label(signals),
        clean_text(item.get("url")),
        tags,
    ]).strip()


def build_summary(top_rows: list[dict[str, Any]], rules: dict[str, Any], site_url: str) -> str:
    if not top_rows:
        return ""
    now = datetime.now(JST)
    lines = [f"【{now.month}/{now.day}】SNS反応から見る、今チェックしたい予約候補"]
    for idx, row in enumerate(top_rows, 1):
        item = row["item"]
        genre_name = clean_text(row["genre"].get("name"))
        short = CATEGORY_COPY.get(genre_name, {}).get("short", genre_name)
        lines.append(f"{idx}. {short} / {core_name(item.get('name', ''), 54)}")
        lines.append(f"   {signal_label(row.get('signals', {}))}")
    lines.append("")
    lines.append(site_url.rstrip("/") + "/")
    tags = []
    for row in top_rows:
        tags.extend(tags_for(row, rules))
    unique = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)
    lines.append(" ".join(unique[:4]))
    return "\n".join(lines).strip()


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    data = read_json(Path(args.data), {})
    rules = read_json(Path(args.rules), {})
    rows = load_rows(data)
    title_keywords = rules.get("title_keywords", [])

    for row in rows:
        row["base_score"] = base_score(row)
        row["terms"] = terms_for_row(row, title_keywords)

    candidates = sorted(rows, key=lambda row: row["base_score"], reverse=True)[: args.max_candidates]
    unique_terms: list[str] = []
    for row in candidates:
        for term in row["terms"]:
            if term not in unique_terms:
                unique_terms.append(term)
            if len(unique_terms) >= args.max_terms:
                break
        if len(unique_terms) >= args.max_terms:
            break

    log(f"[分析] 候補商品 {len(candidates)}件 / SNS検索語 {len(unique_terms)}件")
    signals_by_term = collect_signals(unique_terms, args)

    for row in candidates:
        best_signals: dict[str, int] = {}
        best_social = -1.0
        best_term = ""
        for term in row["terms"]:
            signals = signals_by_term.get(term, {})
            social = score_from_signals(signals)
            if social > best_social:
                best_social = social
                best_signals = signals
                best_term = term
        row["matched_term"] = best_term
        row["signals"] = best_signals
        row["social_score"] = max(0.0, best_social)
        row["score"] = round(row["base_score"] + row["social_score"], 2)
        row["intro"] = build_intro(row, best_signals, rules)

    ranked = sorted(candidates, key=lambda row: row["score"], reverse=True)[: args.limit]
    site_url = os.environ.get("SITE_URL", "").strip() or data.get("site_url", "https://katakanaorijin-byte.github.io/imaure/")
    return {
        "generated_at": datetime.now(JST).isoformat(),
        "hours": args.hours,
        "sources": args.sources,
        "offline": bool(args.offline),
        "summary_post": build_summary(ranked[:3], rules, site_url),
        "items": [
            {
                "rank": idx,
                "score": row["score"],
                "base_score": row["base_score"],
                "social_score": round(row["social_score"], 2),
                "matched_term": row["matched_term"],
                "signals": row["signals"],
                "category": row["genre"].get("name", ""),
                "name": row["item"].get("name", ""),
                "price": row["item"].get("price", 0),
                "url": row["item"].get("url", ""),
                "image": row["item"].get("image", ""),
                "shop": row["item"].get("shop", ""),
                "intro": row["intro"],
            }
            for idx, row in enumerate(ranked, 1)
        ],
    }


def print_result(payload: dict[str, Any]) -> None:
    print(payload["summary_post"])
    print("\n" + "=" * 72 + "\n")
    for item in payload["items"]:
        print(f"#{item['rank']} score={item['score']} term={item['matched_term']}")
        print(item["intro"])
        print("\n" + "-" * 72 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SNS熱量から投稿向け商品と紹介文を作る")
    parser.add_argument("--data", default=str(DATA_PATH), help="商品データJSON")
    parser.add_argument("--rules", default=str(RULES_PATH), help="ハッシュタグ/タイトルルールJSON")
    parser.add_argument("--sources", default="manual,bluesky,reddit,x,youtube",
                        help="使うSNSソース。例: manual,bluesky,reddit,x,youtube")
    parser.add_argument("--signal-file", default="", help="手動SNSシグナルCSV/JSON")
    parser.add_argument("--hours", type=int, default=48, help="SNS反応を見る時間幅")
    parser.add_argument("--limit", type=int, default=5, help="出力する商品数")
    parser.add_argument("--max-candidates", type=int, default=30, help="SNS分析対象にする候補商品数")
    parser.add_argument("--max-terms", type=int, default=36, help="SNS検索する語数の上限")
    parser.add_argument("--delay", type=float, default=0.4, help="SNS検索の間隔秒")
    parser.add_argument("--offline", action="store_true", help="ネット検索せずローカル/手動シグナルだけで作る")
    parser.add_argument("--dry-run", action="store_true", help="ファイルを書かず標準出力だけにする")
    parser.add_argument("--out-json", default=str(DEFAULT_JSON_OUT), help="分析結果JSONの出力先")
    parser.add_argument("--out-text", default=str(DEFAULT_TEXT_OUT), help="投稿文テキストの出力先")
    args = parser.parse_args()

    payload = analyze(args)
    print_result(payload)

    if args.dry_run:
        return
    json_path = Path(args.out_json)
    text_path = Path(args.out_text)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text_path.write_text(payload["summary_post"] + "\n", encoding="utf-8")
    log(f"[出力] {json_path}")
    log(f"[出力] {text_path}")


if __name__ == "__main__":
    main()
