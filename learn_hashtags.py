# -*- coding: utf-8 -*-
"""
docs/data.json の商品名・カテゴリを見て、半自動投稿ツール用のハッシュタグ候補を作る。
外部ライブラリなしで動く軽いルール学習にして、GitHub Actionsでも安定して実行できるようにする。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "docs" / "data.json"
OUT_PATH = HERE / "docs" / "hashtag-rules.json"
JST = timezone(timedelta(hours=9))


DEFAULT_TAGS = ["#予約開始レーダー", "#ホビー予約"]

COPY_RULES = {
    "tag_policy": [
        "ハッシュタグは最大4個まで",
        "商品カテゴリタグを先に置く",
        "サービス名タグは最後に置く",
        "本文には予約開始・新着予約・在庫変動など、検索されやすい語を自然に入れる",
    ],
    "summary_openers": {
        "soft": [
            "{category}の新着予約、気になるものを拾っておきました。",
            "あとで見返しやすいように、{category}まわりの新着をまとめます。",
            "予約まわり、今日も少し動きがありました。",
        ],
        "watch": [
            "{category}まわりに予約開始の動きあり。ざっと確認用です。",
            "見逃しやすい予約開始、{count}件だけまとめてチェックしておきます。",
            "在庫や価格は動きやすいので、気になるものは早めに確認を。",
        ],
        "calm": [
            "必要な人に届けばいいな、くらいの温度で{category}の新着を置いておきます。",
            "急ぎすぎず、でも見落としにくいようにメモしておきます。",
            "{count}件だけ、見やすいように抜き出しました。",
        ],
        "none": [""],
    },
    "single_openers": {
        "soft": [
            "{category}で新着予約を見つけました。",
            "気になる人向けに、{category}の予約情報をひとつメモ。",
            "あとで探し直しやすいように、予約情報を置いておきます。",
        ],
        "watch": [
            "{category}の予約開始を確認しました。",
            "在庫・価格が動きやすそうなので、気になる人は早めに確認を。",
            "見落とし防止用に、{category}の新着予約をピックアップ。",
        ],
        "calm": [
            "必要な人だけ拾ってください。{category}の新着予約です。",
            "ひとまず確認用に、{category}の予約情報を置いておきます。",
            "急がせたいわけではないですが、見逃し防止でメモしておきます。",
        ],
        "none": [""],
    },
}


SEED_RULES = [
    (["ポケモンカード", "ポケカ", "Pokemon", "MEGA", "拡張パック"], ["#ポケカ", "#ポケモンカード"]),
    (["ワンピースカード", "ONE PIECEカード", "ルフィ", "エース"], ["#ワンピースカード"]),
    (["遊戯王", "デュエルモンスターズ"], ["#遊戯王"]),
    (["デュエル・マスターズ", "デュエマ"], ["#デュエマ"]),
    (["フィギュア", "スケールフィギュア", "完成品"], ["#フィギュア"]),
    (["ねんどろいど"], ["#ねんどろいど"]),
    (["figma"], ["#figma"]),
    (["ガンダム", "ガンプラ", "HG", "MG", "RG"], ["#ガンプラ"]),
    (["プラモデル", "プラモ", "模型"], ["#プラモデル"]),
    (["仮面ライダー"], ["#仮面ライダー"]),
    (["ウルトラマン"], ["#ウルトラマン"]),
    (["プリキュア"], ["#プリキュア"]),
    (["ドラゴンボール"], ["#ドラゴンボール"]),
    (["ホロライブ"], ["#ホロライブ"]),
    (["アクリル", "アクスタ", "キーホルダー", "缶バッジ"], ["#グッズ"]),
    (["ぬいぐるみ", "マスコット"], ["#ぬいぐるみ"]),
    (["食玩", "ウエハース"], ["#食玩"]),
    (["ゲーム", "Switch", "PS5"], ["#ゲーム"]),
]


def tag_from_text(text: str) -> str:
    text = re.sub(r"[#＃\s　/／・|｜（）()\[\]【】<>＜＞,，.。:：;；!！?？]+", "", text)
    return f"#{text}" if text else ""


def clean_name(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    genres = data.get("genres", [])

    corpus_parts: list[str] = []
    genre_tags: dict[str, list[str]] = {}
    observed = Counter()

    for genre in genres:
        genre_name = clean_name(genre.get("name"))
        base_tag = clean_name(genre.get("tag")) or tag_from_text(genre_name)
        tags = [base_tag] if base_tag else []
        for keywords, rule_tags in SEED_RULES:
            if any(k.lower() in genre_name.lower() for k in keywords):
                tags.extend(rule_tags)
        genre_tags[genre_name] = list(dict.fromkeys(tags))[:3]

        for item in genre.get("items", []):
            name = clean_name(item.get("name"))
            corpus_parts.append(f"{genre_name} {name}")
            for keywords, rule_tags in SEED_RULES:
                if any(k.lower() in name.lower() for k in keywords):
                    observed.update(rule_tags)

    corpus = "\n".join(corpus_parts).lower()
    keyword_rules = []
    for keywords, tags in SEED_RULES:
        hits = sum(corpus.count(k.lower()) for k in keywords)
        if hits:
            keyword_rules.append({
                "keywords": keywords,
                "tags": tags,
                "score": hits,
            })

    keyword_rules.sort(key=lambda rule: rule["score"], reverse=True)
    learned_popular_tags = [tag for tag, _ in observed.most_common(12)]

    payload = {
        "generated_at": datetime.now(JST).isoformat(),
        "default_tags": DEFAULT_TAGS,
        "genre_tags": genre_tags,
        "keyword_rules": keyword_rules,
        "learned_popular_tags": learned_popular_tags,
        "copy_rules": COPY_RULES,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(HERE)} ({len(keyword_rules)} keyword rules)")


if __name__ == "__main__":
    main()
