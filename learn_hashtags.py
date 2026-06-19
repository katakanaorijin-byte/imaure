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

CATEGORY_COPY = {
    "ポケモンカード": {
        "short": "ポケカ",
        "focus": "BOXや拡張パック",
        "audience": "開封勢・コレクション勢",
        "watch": "在庫や価格差",
    },
    "ワンピースカード": {
        "short": "ワンピカード",
        "focus": "BOXやブースターパック",
        "audience": "デッキ強化勢・コレクター",
        "watch": "再販や予約枠",
    },
    "遊戯王・他カード": {
        "short": "TCG",
        "focus": "BOXやブースターパック",
        "audience": "デュエリスト・カード勢",
        "watch": "予約枠や価格",
    },
    "フィギュア": {
        "short": "フィギュア",
        "focus": "スケールフィギュアや完成品",
        "audience": "推しを飾りたい人",
        "watch": "予約締切や価格",
    },
    "ねんどろいど・figma": {
        "short": "ねんどろいど・figma",
        "focus": "可動・デフォルメ系",
        "audience": "推しを手元に置きたい人",
        "watch": "再販や特典",
    },
    "ガンプラ・プラモデル": {
        "short": "ガンプラ・プラモ",
        "focus": "新作や再販キット",
        "audience": "積みプラ予定の人",
        "watch": "再販枠や在庫",
    },
    "ゲームソフト": {
        "short": "ゲーム予約",
        "focus": "新作ソフトや特典付き",
        "audience": "発売日に遊びたい人",
        "watch": "店舗特典や在庫",
    },
    "アニメBlu-ray・CD": {
        "short": "アニメBD/CD",
        "focus": "初回特典や限定版",
        "audience": "特典まで追いたい人",
        "watch": "予約特典や締切",
    },
    "特撮・なりきり玩具": {
        "short": "特撮玩具",
        "focus": "変身アイテムや関連玩具",
        "audience": "なりきり玩具を追う人",
        "watch": "発売直後の在庫",
    },
    "鉄道模型": {
        "short": "鉄道模型",
        "focus": "Nゲージや車両セット",
        "audience": "編成をそろえたい人",
        "watch": "再生産や予約枠",
    },
    "トミカ・ミニカー": {
        "short": "トミカ・ミニカー",
        "focus": "初回特別仕様や新車",
        "audience": "コレクション勢",
        "watch": "初回仕様や在庫",
    },
    "ぬいぐるみ・グッズ": {
        "short": "キャラグッズ",
        "focus": "ぬいぐるみやアクスタ",
        "audience": "推し活用に探している人",
        "watch": "予約枠や再入荷",
    },
}


def build_category_openers() -> dict[str, dict[str, dict[str, list[str]]]]:
    openers = {}
    for category, rule in CATEGORY_COPY.items():
        short = rule["short"]
        focus = rule["focus"]
        audience = rule["audience"]
        watch = rule["watch"]
        openers[category] = {
            "summary": {
                "soft": [
                    f"{short}の新着予約、{focus}中心に気になる動きを拾いました。",
                    f"{audience}向けに見返しやすく、{category}の予約情報をまとめます。",
                    f"{category}まわり、今日の予約チェック用に少し整理しておきます。",
                ],
                "watch": [
                    f"{short}まわりに予約開始の動きあり。{watch}も変わりやすいので確認用です。",
                    f"{focus}を追っている人向けに、{{count}}件だけまとめてチェックします。",
                    f"{category}はタイミングで見え方が変わるので、気になるものは早めに確認を。",
                ],
                "calm": [
                    f"{audience}に届けばいいな、くらいの温度で{category}の新着を置いておきます。",
                    f"{short}探しのメモとして、見返しやすいようにまとめました。",
                    f"急ぎすぎず、でも見落としにくいように{category}の予約情報を残しておきます。",
                ],
                "none": [""],
            },
            "single": {
                "soft": [
                    f"{short}で{focus}まわりの新着予約を見つけました。",
                    f"{audience}向けに、{category}の予約情報をひとつメモ。",
                    f"{short}探しのメモとして、気になる予約を置いておきます。",
                ],
                "watch": [
                    f"{short}は{watch}が出やすいので、気になる人は早めに確認を。",
                    f"{category}の予約開始を確認。{focus}狙いならチェックしておきたいところです。",
                    f"見落とし防止用に、{short}の新着予約をピックアップ。",
                ],
                "calm": [
                    f"{audience}に届けば十分、{category}の予約情報を静かに置いておきます。",
                    f"急がせたいわけではないですが、{short}の確認用にメモしておきます。",
                    f"{category}まわり、あとで探し直しやすいようにひとつ残しておきます。",
                ],
                "none": [""],
            },
        }
    return openers


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
    "category_openers": build_category_openers(),
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
    (["ゲームソフト", "Switch", "PS5", "Nintendo Switch", "プレイステーション"], ["#ゲーム"]),
]


# 商品名の「主な部分」を残すための学習用。タイトル語(作品名・シリーズ名)を守り、
# 商品の種類を表す一般語(パック等)はタイトル扱いしない。
TITLE_STOP = {
    "ブースターパック", "ブースター", "パック", "ボックス", "カートン", "セット",
    "フィギュア", "プラモデル", "プラモ", "モデル", "キット", "プライズ", "スケール",
    "クーポン", "ポイント", "シリーズ", "バージョン", "エディション", "スターター",
    "デッキ", "ストレージ", "スリーブ", "ホビー", "アイテム", "グッズ", "コレクション",
    "ニンテンドー", "スイッチ", "ソフト", "コントローラー", "ヘッドセット", "ポーチ",
    "カバー", "ケース", "クリア", "ラバー", "アクリル", "スタンド", "キーホルダー",
    "ストラップ", "オリジナル", "リミテッド", "プレミアム", "コンプリート",
    "ディスプレイ", "ジオラマ", "ミニチュア", "ドールハウス", "ランダム",
    # 宣伝・汎用語(タイトルではないので除外。先頭ノイズ除去を妨げないため)
    "レビュー", "レビュー特典", "ショップ", "ストア", "センター", "プレゼント",
    "ライセンス", "ラッピング", "シュリンク", "トップローダー", "キャンペーン",
    "ノベルティ", "ラインナップ", "イラスト", "キャラクター", "リニューアル",
    "ホワイト", "ブラック", "ブルーグレー", "カラー", "ソーラー", "トリプル",
    "ドリーム", "ヨーロッパ", "タイトル", "リアルフィギュア", "プレステージモデル",
}
SEED_TITLES = [
    "推しの子", "葬送のフリーレン", "鬼滅の刃", "呪術廻戦", "ワンピース", "ドラゴンボール",
    "ポケモン", "ガンダム", "エヴァンゲリオン", "初音ミク", "ブルーアーカイブ", "ホロライブ",
    "にじさんじ", "ウマ娘", "原神", "崩壊スターレイル", "スプラトゥーン", "ゼルダの伝説",
    "あつまれ どうぶつの森", "どうぶつの森", "チェンソーマン", "SPY×FAMILY", "ハイキュー",
    "ヴァイスシュヴァルツ", "遊戯王", "デュエルマスターズ", "僕のヒーローアカデミア",
    "名探偵コナン", "ちいかわ", "サンリオ", "アイドルマスター", "ラブライブ", "仮面ライダー",
    "ウルトラマン", "プリキュア", "フリーレン",
]
KATAKANA_RUN = re.compile(r"[ァ-ヶー]{4,}")
_TITLE_BAD_PART = ("パック", "ボックス", "セット", "クーポン", "シリーズ", "バージョン")


def learn_title_keywords(corpus_parts):
    """商品名から作品名・シリーズ名らしい語を頻度学習する(商品名の主な部分を守るため)。"""
    counter = Counter()
    for part in corpus_parts:
        for run in KATAKANA_RUN.findall(part):
            if run in TITLE_STOP or any(bad in run for bad in _TITLE_BAD_PART):
                continue
            counter[run] += 1
    keywords = [word for word, hits in counter.most_common(80) if hits >= 2]
    for seed in SEED_TITLES:
        if seed not in keywords and any(seed in part for part in corpus_parts):
            keywords.append(seed)
    return keywords


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
    title_keywords = learn_title_keywords(corpus_parts)

    payload = {
        "generated_at": datetime.now(JST).isoformat(),
        "default_tags": DEFAULT_TAGS,
        "genre_tags": genre_tags,
        "keyword_rules": keyword_rules,
        "learned_popular_tags": learned_popular_tags,
        "title_keywords": title_keywords,
        "copy_rules": COPY_RULES,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(HERE)} ({len(keyword_rules)} keyword rules, {len(title_keywords)} title keywords)")


if __name__ == "__main__":
    main()
