# -*- coding: utf-8 -*-
"""
いまウレ! SNS自動投稿ツール
docs/data.json(generate.pyが作る最新ランキング)を読んで、
X(旧Twitter)とThreadsに「今日の売れ筋TOP3」を自動投稿します。

必要な環境変数(設定したSNSにだけ投稿します):
  X(旧Twitter):
    X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET
  Threads:
    THREADS_ACCESS_TOKEN
  共通(任意):
    SITE_URL  … 投稿に載せるサイトURL(data.json側に入っていれば不要)

どちらのキーも無ければ、何もせず正常終了します(エラーにしない)。
"""

import base64
import hashlib
import hmac
import argparse
import json
import os
import secrets as pysecrets
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ============================================================
# 投稿文を作る
# ============================================================

# 毎日同じ文面だとスパム扱いされやすいので、日替わりで言い回しを変える
HEADERS = [
    "予約開始キャッチ🆕",
    "新規予約はじまってます📡",
    "本日の予約開始レーダー🚨",
    "予約スタート速報🏃",
]
FOOTERS = [
    "👇全カテゴリの新着予約(15分ごと監視)",
    "👇フィギュア・ガンプラ・ゲームの新着も",
    "👇受付中の全リストはこちら",
    "👇売り切れ前にチェック",
]

SUMMARY_TAGS = ["#予約開始", "#ホビー予約", "#再販", "#抽選"]
SUMMARY_FIXED_TAGS = ["#予約開始", "#ホビー予約", "#ポケカ", "#ガンプラ"]
SHORT_CATEGORY_NAMES = {
    "ポケモンカード": "ポケカ",
    "ワンピースカード": "ワンピカード",
    "ガンプラ・プラモデル": "ガンプラ",
    "アニメBlu-ray・CD": "アニメBD/CD",
    "遊戯王・他カード": "遊戯王",
    "ねんどろいど・figma": "ねんどろいど",
}


MAX_POSTS_PER_DAY = 4   # Xの無料枠(月500投稿)に対し最大120/月で安全圏
MIN_GAP_MINUTES = 90    # 連投によるスパム判定を避ける最低間隔
STATE_PATH = os.path.join(HERE, "docs", "post_state.json")


def load_state():
    today = datetime.now(JST).strftime("%Y-%m-%d")
    state = {"date": today, "count": 0, "last": "", "posted": []}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            s = json.load(f)
        if s.get("date") == today:
            state.update({k: s.get(k, state[k]) for k in ("date", "count", "last")})
        state["posted"] = s.get("posted", [])[:200]  # 投稿済みIDは日をまたいでも保持
    except Exception:
        pass
    return state


def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        print(f"状態保存に失敗: {e}", file=sys.stderr)


def x_weighted_len(text: str) -> int:
    """Xの文字数カウント(日本語などは2文字換算、URLは23文字換算)"""
    total = 0
    for part in text.split():
        if part.startswith("http://") or part.startswith("https://"):
            total += 23 + 1
            continue
        for ch in part:
            total += 1 if ord(ch) < 0x1100 else 2
        total += 1
    return total


def trim(name: str, limit: int) -> str:
    name = " ".join(name.split())
    return name if len(name) <= limit else name[: limit - 1] + "…"


def _busted(url: str) -> str:
    """Xのリンクカードを日替わりで更新させる。
    毎時バストするとXが毎回コールドスクレイプを強いられ、楽天画像の取得失敗で
    カード画像が出ないことがあるため、1日1回(=Xのキャッシュを使い回せる粒度)に抑える。"""
    if not url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}ref={datetime.now(JST).strftime('%Y%m%d')}"


def build_post(data: dict, name_limit: int, posted=frozenset()):
    """未投稿の新着予約から速報文を作る。対象が無ければ None(投稿しない)"""
    now = datetime.now(JST)
    day_seed = int(now.strftime("%j")) + now.hour  # 同日内でも言い回しが変わる
    header = HEADERS[day_seed % len(HEADERS)]
    footer = FOOTERS[day_seed % len(FOOTERS)]
    site_url = os.environ.get("SITE_URL", "").strip() or data.get("site_url", "")

    fresh = [it for g in data["genres"] for it in g["items"]
             if it.get("is_new") and it.get("url") not in posted]
    if not fresh:
        return None

    lines = [f"【{now.month}/{now.day}】{header} 新着{len(fresh)}件"]
    shown, tags, used = 0, [], []
    for g in data["genres"]:
        if shown >= 3:
            continue
        first = next((it for it in g["items"]
                      if it.get("is_new") and it.get("url") not in posted), None)
        if not first:
            continue
        rel = f"({first['release']}発売)" if first.get("release") else ""
        lines.append(f"{g.get('icon', '・')} {trim(first['name'], name_limit)}{rel}")
        used.append(first.get("url", ""))
        if g.get("tag"):
            tags.append(g["tag"])
        shown += 1
    if not used:
        return None
    lines.append(footer)
    if site_url:
        lines.append(_busted(site_url))
    lines.append(" ".join(["#予約開始"] + tags[:3]))
    return "\n".join(lines), used


def build_post_for_x(data: dict, posted=frozenset()):
    """Xは280字(日本語は2字換算)に収まるまで商品名を短くする"""
    result = None
    for limit in (26, 20, 15, 11):
        result = build_post(data, limit, posted)
        if result is None or x_weighted_len(result[0]) <= 275:
            return result
    return result  # それでも超える場合は最後の短縮版で送る


def _site_url(data: dict) -> str:
    return (os.environ.get("SITE_URL", "").strip() or data.get("site_url", "")).rstrip("/") + "/"


def _category_sample(data: dict, limit=4):
    cats = []
    for g in data.get("genres", []):
        if g.get("items"):
            name = g.get("name", "")
            cats.append((g.get("icon", "・"), SHORT_CATEGORY_NAMES.get(name, name), g.get("tag", "")))
        if len(cats) >= limit:
            break
    return cats


def build_summary_post(data: dict, mode: str, name_limit=16):
    """weekly/monthly/profile の投稿文を作る。"""
    site_url = _site_url(data)
    now = datetime.now(JST)
    cats = _category_sample(data, 4)
    tags = []
    for _, _, tag in cats:
        if tag:
            tags.append(tag)

    if mode == "profile":
        url = site_url
        lines = [
            "予約開始レーダーでは、ホビーの予約開始・再販・抽選情報を自動チェックしています。",
            "",
            "ポケカ / ガンプラ / フィギュア / ゲームなど、受付中の予約一覧をまとめて確認できます。",
            url,
            "#予約開始 #ホビー予約",
        ]
        return "\n".join(lines), ["profile"]

    is_weekly = mode == "weekly"
    label = "今週" if is_weekly else "今月"
    path = "weekly/" if is_weekly else "monthly/"
    url = _busted(site_url + path)
    cat_text = " / ".join(trim(name, name_limit) for _, name, _ in cats)
    lines = [
        f"{label}のホビー予約開始まとめを更新しました。",
        "",
        f"{cat_text}など、",
        "予約開始・再販・抽選情報をカテゴリ別に整理しています。",
        "",
        url,
        " ".join(SUMMARY_FIXED_TAGS),
    ]
    return "\n".join(lines), [mode]


def build_summary_post_for_x(data: dict, mode: str):
    result = None
    for limit in (18, 14, 10):
        result = build_summary_post(data, mode, name_limit=limit)
        if x_weighted_len(result[0]) <= 275:
            return result
    return result


def summary_state_key(mode: str) -> str:
    now = datetime.now(JST)
    if mode == "weekly":
        y, w, _ = now.isocalendar()
        return f"summary:weekly:{y}-W{w:02d}"
    if mode == "monthly":
        return f"summary:monthly:{now:%Y-%m}"
    return "summary:profile"


# ============================================================
# X(旧Twitter)へ投稿  ※OAuth 1.0a署名を自前実装(追加ライブラリ不要)
# ============================================================

def _pct(s: str) -> str:
    return urllib.parse.quote(str(s), safe="")


def post_to_x(text: str) -> bool:
    api_key = os.environ.get("X_API_KEY", "").strip()
    api_secret = os.environ.get("X_API_SECRET", "").strip()
    token = os.environ.get("X_ACCESS_TOKEN", "").strip()
    token_secret = os.environ.get("X_ACCESS_SECRET", "").strip()
    if not all([api_key, api_secret, token, token_secret]):
        print("X: キー未設定のためスキップします")
        return False

    url = "https://api.twitter.com/2/tweets"
    oauth = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": pysecrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    # 署名のもとになる文字列を作る(JSON本文は署名対象に含めない決まり)
    param_str = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in sorted(oauth.items()))
    base = "&".join(["POST", _pct(url), _pct(param_str)])
    signing_key = f"{_pct(api_secret)}&{_pct(token_secret)}".encode()
    sig = base64.b64encode(hmac.new(signing_key, base.encode(), hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = sig

    auth_header = "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": auth_header, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            result = json.loads(res.read().decode())
        print(f"X: 投稿しました → id {result.get('data', {}).get('id')}")
        return True
    except urllib.error.HTTPError as e:
        print(f"X: 投稿失敗 ({e.code}) {e.read().decode()[:300]}", file=sys.stderr)
        return False


# ============================================================
# Threadsへ投稿(公式 Threads API)
# ============================================================

THREADS_API = "https://graph.threads.net/v1.0"


def _threads_post(path: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{THREADS_API}/{path}", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode())


def post_to_threads(text: str) -> bool:
    token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if not token:
        print("Threads: トークン未設定のためスキップします")
        return False

    try:
        # 1) 自分のユーザーIDを取得
        q = urllib.parse.urlencode({"fields": "id", "access_token": token})
        with urllib.request.urlopen(f"{THREADS_API}/me?{q}", timeout=30) as res:
            user_id = json.loads(res.read().decode())["id"]

        # 2) 投稿の下書き(コンテナ)を作る
        container = _threads_post(
            f"{user_id}/threads",
            {"media_type": "TEXT", "text": text, "access_token": token},
        )
        time.sleep(3)  # 反映待ち(公式推奨)

        # 3) 公開する
        result = _threads_post(
            f"{user_id}/threads_publish",
            {"creation_id": container["id"], "access_token": token},
        )
        print(f"Threads: 投稿しました → id {result.get('id')}")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"Threads: 投稿失敗 ({e.code}) {body}", file=sys.stderr)
        if "expired" in body.lower() or e.code in (401, 403, 190):
            print("Threads: トークン期限切れの可能性。説明書の手順で再発行してください。", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Threads: 投稿失敗 {e}", file=sys.stderr)
        return False


# ============================================================
# メイン
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="予約開始レーダー SNS投稿ツール")
    parser.add_argument(
        "--mode",
        choices=("fresh", "weekly", "monthly", "profile"),
        default=os.environ.get("POST_MODE", "fresh"),
        help="fresh=新着速報、weekly/monthly=まとめ投稿、profile=固定ポスト用文面",
    )
    parser.add_argument("--dry-run", action="store_true", help="投稿せず文面だけ表示")
    return parser.parse_args()


def main():
    args = parse_args()
    data_path = os.path.join(HERE, "docs", "data.json")
    if not os.path.exists(data_path):
        print("data.json がありません。先に generate.py を実行してください。", file=sys.stderr)
        sys.exit(1)

    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    if data.get("demo"):
        print("デモデータのため投稿しません(楽天APIキーを設定すると投稿が始まります)")
        return

    state = load_state()
    posted = set(state["posted"])

    if args.mode in ("weekly", "monthly", "profile"):
        text, used = build_summary_post_for_x(data, args.mode)
        print(f"--- {args.mode} 投稿文 ---\n{text}\n-------------------")
        if args.dry_run:
            return
        key = summary_state_key(args.mode)
        if key in posted:
            print(f"{args.mode}: 投稿済みのためスキップします({key})")
            return
        ok = 0
        has_x = bool(os.environ.get("X_API_KEY"))
        has_threads = bool(os.environ.get("THREADS_ACCESS_TOKEN"))
        if not has_x and not has_threads:
            print("SNSキーが未設定なので投稿はスキップしました")
            return
        if has_x and post_to_x(text):
            ok += 1
        if has_threads and post_to_threads(text):
            ok += 1
        if ok:
            state["posted"] = list(dict.fromkeys([key] + state["posted"]))[:200]
            save_state(state)
        print(f"投稿完了: {ok}件")
        return

    # --- 投稿スロットル(常時監視でもSNSを荒らさないための3つの安全装置) ---
    if build_post(data, 20, posted) is None:
        print("未投稿の新着予約がないため投稿しません(重複防止)")
        return
    if args.dry_run:
        rx = build_post_for_x(data, posted)
        if rx:
            print("--- fresh 投稿文 ---\n" + rx[0] + "\n-------------------")
        return

    has_x = bool(os.environ.get("X_API_KEY"))
    has_threads = bool(os.environ.get("THREADS_ACCESS_TOKEN"))
    if not has_x and not has_threads:
        print("SNSキーが未設定なので投稿はスキップしました(サイト更新のみ)")
        return
    if state["count"] >= MAX_POSTS_PER_DAY:
        print(f"本日の投稿上限({MAX_POSTS_PER_DAY}回)に達したため見送り(明日リセット)")
        return
    if state["last"]:
        try:
            gap = (datetime.now(JST) - datetime.fromisoformat(state["last"])).total_seconds() / 60
            if gap < MIN_GAP_MINUTES:
                print(f"前回投稿から{int(gap)}分のため見送り(最低{MIN_GAP_MINUTES}分間隔)")
                return
        except Exception:
            pass

    ok, used_all = 0, set()
    if has_x:
        rx = build_post_for_x(data, posted)
        if rx:
            text_x, used_x = rx
            print("--- Xへの投稿文 ---\n" + text_x + "\n-------------------")
            if post_to_x(text_x):
                ok += 1
                used_all.update(used_x)
    if has_threads:
        rt = build_post(data, name_limit=34, posted=posted)  # Threadsは500字までなので長めでOK
        if rt:
            text_t, used_t = rt
            print("--- Threadsへの投稿文 ---\n" + text_t + "\n-------------------")
            if post_to_threads(text_t):
                ok += 1
                used_all.update(used_t)

    if ok:
        state["count"] += 1
        state["last"] = datetime.now(JST).isoformat()
        state["posted"] = list(dict.fromkeys(list(used_all) + state["posted"]))[:200]
        save_state(state)
    print(f"投稿完了: {ok}件 / 本日{state['count']}回目")


if __name__ == "__main__":
    main()
