# -*- coding: utf-8 -*-
"""
予約開始レーダー サイト自動生成スクリプト

楽天市場のホビーカテゴリを毎日「新着順」でチェックし、
昨日までは存在しなかった商品 = 「予約が始まったばかりの商品」を自動検知します。
一度見た商品は docs/seen.json に記録され、翌日以降の差分判定に使われます。
横断検索バー(楽天+Yahoo!)は search_assets.py から読み込みます。

使い方:
  RAKUTEN_APP_ID と RAKUTEN_ACCESS_KEY と RAKUTEN_AFFILIATE_ID を環境変数に入れて実行
    python generate.py
  未設定ならデモデータで生成します(見た目確認用)。

【注意】RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY はサーバー側の商品巡回専用です(ブラウザには出ません)。
楽天の現行APIはこの2つをセットで要求するため、accessKeyを安全に置けないブラウザから
楽天市場の全商品を直接検索することはできません。
SEARCH_API_URL(別途用意するCloudflare Workers等の中継API。worker/ディレクトリ参照)を設定すると、
横断検索バーが中継APIを通じて楽天・Yahoo!の全商品を検索できるようになります。
未設定の場合は、横断検索バーは「サイト内で検知済みの商品」だけを検索し、それ以外は
楽天市場の検索リンクへ案内します(YAHOO_APP_ID があればYahoo!だけは直接全件検索できます)。
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from html import escape

import calendar_page

from search_assets import SEARCH_CSS, SEARCH_HTML, SEARCH_JS

# ============================================================
# 設定
# ============================================================

SITE_NAME = "予約開始レーダー"
SITE_TAGLINE = "ホビーの“予約開始”を毎日自動キャッチ"
SITE_DESCRIPTION = "ポケモンカード・ワンピースカード・フィギュア・ガンプラ・ゲームソフトの予約開始情報を毎日自動更新。昨日まで無かった新着予約だけを検知して速報します。"
_SITE_URL_ENV = os.environ.get("SITE_URL", "").strip()
SITE_URL = (_SITE_URL_ENV.rstrip("/") + "/") if _SITE_URL_ENV else ""  # 公開URL(空でもOK)
OPERATOR_NAME = os.environ.get("OPERATOR_NAME", "").strip() or "予約開始レーダー運営"
CONTACT_URL = os.environ.get("CONTACT_URL", "").strip()
X_ACCOUNT_URL = os.environ.get("X_ACCOUNT_URL", "").strip()

ITEMS_PER_CATEGORY = 14   # 各カテゴリに表示する件数
FETCH_PAGES = 2           # 楽天から取得するページ数(1ページ30件)
SEEN_KEEP_DAYS = 120      # 既出商品の記録を保持する日数

# 監視カテゴリ(keyword: 楽天で検索する言葉 / ng: 除外する言葉)
CATEGORIES = [
    {"name": "ポケモンカード", "icon": "🃏", "slug": "pokemon-card", "tag": "#ポケカ", "keyword": "ポケモンカード 予約 BOX",
     "ng": "中古 オリパ スリーブ デッキシールド プレイマット", "min_price": 3000},
    {"name": "ワンピースカード", "icon": "🏴", "slug": "onepiece-card", "tag": "#ワンピースカード", "keyword": "ワンピースカード 予約 BOX",
     "ng": "中古 オリパ スリーブ プレイマット", "min_price": 3000},
    {"name": "遊戯王・他カード", "icon": "🎴", "slug": "yugioh", "tag": "#遊戯王", "keyword": "遊戯王 予約 BOX",
     "ng": "中古 オリパ スリーブ プレイマット", "min_price": 2500},
    {"name": "フィギュア", "icon": "🎎", "slug": "figure", "tag": "#フィギュア", "keyword": "フィギュア 予約",
     "ng": "中古 ガチャ 開封済 台座のみ", "min_price": 3000},
    {"name": "ねんどろいど・figma", "icon": "🪆", "slug": "nendoroid", "tag": "#ねんどろいど", "keyword": "ねんどろいど 予約",
     "ng": "中古 開封済", "min_price": 3000},
    {"name": "ガンプラ・プラモデル", "icon": "🤖", "slug": "gunpla", "tag": "#ガンプラ", "keyword": "ガンプラ 予約",
     "ng": "中古 ジャンク 素組 完成品", "min_price": 1500},
    {"name": "ゲームソフト", "icon": "🎮", "slug": "game", "tag": "#ゲーム", "keyword": "ゲームソフト 予約 特典",
     "keywords": ["スプラトゥーン 予約", "Splatoon 予約", "amiibo 予約", "Switch2 ソフト 予約", "任天堂 Switch 予約"],
     "ng": "中古 レンタル", "min_price": 3000},
    {"name": "アニメBlu-ray・CD", "icon": "💿", "slug": "anime-bd", "tag": "#アニメ", "keyword": "アニメ Blu-ray 予約 特典",
     "ng": "中古 レンタル落ち", "min_price": 3500},
    {"name": "特撮・なりきり玩具", "icon": "🦸", "slug": "tokusatsu", "tag": "#仮面ライダー", "keyword": "仮面ライダー 予約 おもちゃ",
     "ng": "中古 ジャンク", "min_price": 2500},
    {"name": "鉄道模型", "icon": "🚃", "slug": "train-model", "tag": "#鉄道模型", "keyword": "鉄道模型 予約",
     "ng": "中古 ジャンク", "min_price": 3000},
    {"name": "トミカ・ミニカー", "icon": "🚗", "slug": "tomica", "tag": "#トミカ", "keyword": "トミカ 予約",
     "ng": "中古 ジャンク", "min_price": 800},
    {"name": "ぬいぐるみ・グッズ", "icon": "🧸", "slug": "plush", "tag": "#ぬいぐるみ", "keyword": "ぬいぐるみ 予約 キャラクター",
     "ng": "中古 訳あり", "min_price": 1500},
]

CATEGORY_DESCRIPTIONS = {
    "ポケモンカード": "BOX予約・抽選開始・再販の動きが早いカテゴリです。新弾発表後は価格差と販売店ごとの特典有無を特に確認してください。",
    "ワンピースカード": "人気弾は予約開始直後に在庫が動きやすいため、BOX販売・抽選販売・再入荷の違いを見ながら追跡します。",
    "遊戯王・他カード": "遊戯王OCGを中心に、カード系ホビーの予約・BOX販売・限定セットを広く拾います。",
    "フィギュア": "スケールフィギュアや限定特典付き商品の予約情報を確認します。価格が高めなので、安い順や価格帯指定が便利です。",
    "ねんどろいど・figma": "再販や特典付き予約が多いカテゴリです。キャラクター名で検索し、受付中の商品を絞り込むのがおすすめです。",
    "ガンプラ・プラモデル": "新作・再販・限定キットの動きが速いカテゴリです。定価に近い予約先を見つける用途を重視しています。",
    "ゲームソフト": "Switch/PS5などの新作、限定版、店舗特典付き予約を追います。マリオやカービィなど作品名検索も活用してください。",
    "アニメBlu-ray・CD": "初回限定盤や店舗別特典付き商品の予約確認向けです。発売日が近い商品は在庫変動に注意してください。",
    "特撮・なりきり玩具": "変身ベルト、フィギュアーツ、限定玩具などの予約開始を拾います。放送・イベント発表後は動きが増えます。",
    "鉄道模型": "Nゲージ/HOゲージの新製品や再生産予約を確認します。価格帯を指定すると探しやすくなります。",
    "トミカ・ミニカー": "初回特別仕様、限定セット、予約開始直後の商品を中心に確認します。",
    "ぬいぐるみ・グッズ": "キャラクターグッズやぬいぐるみの予約受付を拾います。作品名やキャラクター名で検索すると便利です。",
}

API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))

# 15分ごとの常時監視のうち、6時・12時・18時の回だけ「フル便」
# (取得ページ数2倍+Google Trends解析)。それ以外は軽量便で外部負荷を抑える
FULL_HOURS = (6, 12, 18)


def is_full_run():
    if os.environ.get("FORCE_FULL"):
        return True
    now = datetime.now(JST)
    return now.hour in FULL_HOURS and now.minute < 15


# ============================================================
# 商品名から「発売時期」を読み取る
# ============================================================

def parse_release(name: str):
    """商品名から発売・発送時期を抜き出す(例:「2026年8月下旬発売」→「8月下旬」)"""
    t = unicodedata.normalize("NFKC", name)
    m = re.search(
        r"((?:20\d{2}年)?\s*\d{1,2}月\s*(?:上旬|中旬|下旬|末)?)\s*(?:頃|以降)?\s*(?:発売|発送|出荷|入荷|お届け)",
        t)
    if m:
        return re.sub(r"\s", "", m.group(1))
    m = re.search(r"発売日\s*[:：]?\s*((?:20\d{2}年)?\d{1,2}月\d{1,2}日?)", t)
    if m:
        return m.group(1)
    return ""


def _parse_seen(ts: str):
    """seen.jsonの日時(旧形式の日付のみにも対応)をdatetimeに"""
    try:
        if len(ts) == 10:  # 旧形式 "YYYY-MM-DD"
            ts += "T06:00"
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M").replace(tzinfo=JST)
    except Exception:
        return None


def is_recent(ts: str, hours=24) -> bool:
    d = _parse_seen(ts)
    return d is not None and (datetime.now(JST) - d) <= timedelta(hours=hours)


def ago_text(ts: str) -> str:
    """「12分前」「5時間前」「6/11掲載」のような鮮度表示を作る"""
    d = _parse_seen(ts)
    if d is None:
        return ""
    mins = int((datetime.now(JST) - d).total_seconds() // 60)
    if mins < 60:
        return f"{max(mins, 1)}分前"
    if mins < 24 * 60:
        return f"{mins // 60}時間前"
    return f"{d.month}/{d.day}掲載"


def is_released_item(it, now) -> bool:
    """商品名から読み取った発売時期が今日より前なら「発売済み」とみなす
    (商品名に「予約」が残っていても、出品者がタイトルを更新していないだけで
    実際は発売済み・通常販売になっていることが多いため)"""
    parsed = calendar_page.parse_release_key(it.get("release", ""), now)
    if not parsed:
        return False  # 発売時期が読み取れない場合は安全側で「予約中」に残す
    return parsed[0] < (now.year, now.month, now.day)


# ============================================================
# データ取得と新着判定
# ============================================================

def fetch_rakuten(app_id, access_key, affiliate_id, cat, pages=FETCH_PAGES):
    """楽天検索APIを新着順で叩き、「予約」商品だけ集める"""
    items, seen_codes = [], set()
    keywords = list(dict.fromkeys([cat["keyword"]] + cat.get("keywords", [])))
    for keyword in keywords:
        for page in range(1, pages + 1):
            params = {
                "applicationId": app_id, "accessKey": access_key, "format": "json", "formatVersion": 2,
                "keyword": keyword, "NGKeyword": cat["ng"],
                "hits": 30, "page": page,
                "sort": "-updateTimestamp",  # 新着・更新が新しい順
                "availability": 1, "minPrice": cat["min_price"],
            }
            if affiliate_id:
                params["affiliateId"] = affiliate_id
            url = API_URL + "?" + urllib.parse.urlencode(params)
            headers = {"User-Agent": "yoyaku-radar-generator"}
            if SITE_URL:
                headers["Referer"] = SITE_URL
                headers["Referrer"] = SITE_URL
                headers["Origin"] = SITE_URL.rstrip("/")
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as res:
                    data = json.loads(res.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    body = ""
                print(f"[警告] {cat['name']} {keyword} p{page} 取得失敗: HTTP {e.code} {body}", file=sys.stderr)
                data = {}
            except Exception as e:
                print(f"[警告] {cat['name']} {keyword} p{page} 取得失敗: {e}", file=sys.stderr)
                data = {}
            for e in data.get("Items") or data.get("items") or []:
                it = e.get("Item") or e.get("item") or e
                code = it.get("itemCode", "")
                name = it.get("itemName", "")
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)
                if "予約" not in name:   # 商品名に「予約」が無いものは除外(精度優先)
                    continue
                image = ""
                if it.get("mediumImageUrls"):
                    first_image = it["mediumImageUrls"][0]
                    if isinstance(first_image, dict):
                        image = first_image.get("imageUrl", "")
                    else:
                        image = str(first_image or "")
                    image = image.replace("?_ex=128x128", "?_ex=300x300")
                items.append({
                    "code": code,
                    "name": name,
                    "price": int(it.get("itemPrice", 0) or 0),
                    "shop": it.get("shopName", ""),
                    "url": it.get("affiliateUrl") or it.get("itemUrl", ""),
                    "image": image,
                    "release": parse_release(name),
                    "review_count": int(it.get("reviewCount", 0) or 0),
                })
            time.sleep(1.2)  # 楽天のルール(1秒1回まで)を守る
    return items


def demo_category(cat):
    months = ["7月下旬", "8月上旬", "8月下旬", "9月中旬", "10月発売予定", ""]
    items = []
    for i in range(ITEMS_PER_CATEGORY):
        rel = months[i % len(months)]
        rel_txt = f" {rel}発売" if rel else ""
        items.append({
            "code": f"demo:{cat['name']}:{i}",
            "name": f"【予約】{cat['name']} 新作アイテム 第{i + 1}弾{rel_txt} 特典付き",
            "price": 4500 + i * 830,
            "shop": "サンプルホビー店",
            "url": "https://www.rakuten.co.jp/",
            "image": "",
            "release": rel.replace("発売予定", ""),
            "review_count": 0,
        })
    return items


def load_seen():
    path = os.path.join(HERE, "docs", "seen.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def collect_data():
    app_id = os.environ.get("RAKUTEN_APP_ID", "").strip()
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY", "").strip()
    affiliate_id = os.environ.get("RAKUTEN_AFFILIATE_ID", "").strip()
    demo = not (app_id and access_key)
    print(f"楽天API設定: app_id={'あり' if app_id else 'なし'} access_key={'あり' if access_key else 'なし'} site_url={'あり' if SITE_URL else 'なし'}")
    if not os.environ.get("YAHOO_APP_ID", "").strip():
        print("[警告] YAHOO_APP_ID が未設定のため、検索バーのYahoo!検索は無効化されます。", file=sys.stderr)
    now = datetime.now(JST)
    now_iso = now.strftime("%Y-%m-%dT%H:%M")
    cutoff = (now - timedelta(days=SEEN_KEEP_DAYS)).strftime("%Y-%m-%d")

    seen = load_seen()
    first_run_cats = []
    result = []

    # 直近の予約トレンドワードを取得して「🔥注目」判定に使う
    hot_words = []
    try:
        import trends as _tr
        feed_path = os.path.join(HERE, "docs", "feed_items.json")
        if os.path.exists(feed_path):
            with open(feed_path, encoding="utf-8") as f:
                hot_words = [w for w, c, _ in _tr.own_trends(json.load(f)) if len(w) >= 3][:8]
    except Exception:
        pass

    for cat in CATEGORIES:
        pages = FETCH_PAGES if is_full_run() else 1
        items = demo_category(cat) if demo else fetch_rakuten(app_id, access_key, affiliate_id, cat, pages)
        cat_seen = seen.setdefault(cat["name"], {})
        first_run = len(cat_seen) == 0  # 初回はすべて「新着」になってしまうのを防ぐ

        for it in items:
            first_seen = cat_seen.get(it["code"])
            if first_seen is None:
                first_seen = now_iso
                cat_seen[it["code"]] = now_iso
            it["first_seen"] = first_seen
            it["is_new"] = is_recent(first_seen, hours=24) and not first_run and not demo
            it["hot"] = any(w in it["name"] for w in hot_words)
            it["released"] = is_released_item(it, now)

        if first_run and not demo:
            first_run_cats.append(cat["name"])

        # 新着を先頭に、その後は初登場日が新しい順
        items.sort(key=lambda x: (not x["is_new"], x["first_seen"]), reverse=False)
        items.sort(key=lambda x: x["first_seen"], reverse=True)
        items.sort(key=lambda x: not x["is_new"])

        # 発売時期が過ぎた商品(タイトルは「予約」のままでも実質発売済み)は別ページへ
        active_items = [it for it in items if not it["released"]][:ITEMS_PER_CATEGORY]
        released_items = [it for it in items if it["released"]][:ITEMS_PER_CATEGORY]

        # 古い記録を掃除
        for code in [c for c, d in cat_seen.items() if d[:10] < cutoff]:
            del cat_seen[code]

        if active_items or released_items:
            result.append({**cat, "items": active_items, "released_items": released_items,
                            "new_count": sum(1 for i in active_items if i["is_new"])})
        else:
            print(f"[警告] {cat['name']}: 商品なし(今回はスキップ)", file=sys.stderr)

    if first_run_cats:
        print(f"初回記録モード: {', '.join(first_run_cats)} (明日から新着判定が始まります)")
    return result, seen, demo


# ============================================================
# HTML生成
# ============================================================

AMAZON_TAG = os.environ.get("AMAZON_PARTNER_TAG", "").strip()


def amazon_link(item_name: str) -> str:
    """商品名からAmazon検索リンクを作る(アソシエイトタグ付き)。タグ未設定なら空"""
    if not AMAZON_TAG:
        return ""
    q = re.sub(r"【[^】]*】|\[[^\]]*\]", " ", item_name)          # 【予約】等の飾りを除去
    q = re.sub(r"予約|送料無料|特典付き?|あす楽", " ", q)
    q = " ".join(q.split())[:40]
    url = "https://www.amazon.co.jp/s?" + urllib.parse.urlencode({"k": q, "tag": AMAZON_TAG})
    return (f'<a class="cta amzn" href="{escape(url, quote=True)}" target="_blank" '
            f'rel="nofollow sponsored noopener">Amazonで探す</a>')


def yen(n):
    return f"{int(n):,}"


def render_item(it, cat=None):
    img = (f'<img src="{escape(it["image"], quote=True)}" alt="" loading="lazy">'
           if it["image"] else '<div class="noimg">No<br>Image</div>')
    chips = []
    if cat:
        chips.append(f'<span class="chip-cat">{cat["icon"]} {escape(cat["name"])}</span>')
    if it["is_new"]:
        chips.append('<span class="chip-new">NEW</span>')
    if it.get("hot"):
        chips.append('<span class="chip-hot">注目</span>')
    if it["release"]:
        chips.append(f'<span class="chip-rel">{escape(it["release"])}発売</span>')
    chips_html = f'<p class="cchips">{"".join(chips)}</p>' if chips else ""
    ago = ago_text(it["first_seen"])
    if it["is_new"] and ago:
        ago_html = f'<span class="fresh">⏱ {ago}にキャッチ</span>'
    elif ago:
        ago_html = f'<span class="seen">{ago}</span>'
    else:
        ago_html = ""
    classes = ["card"]
    if it["is_new"]:
        classes.append("isnew")
    if it.get("hot"):
        classes.append("ishot")
    if it.get("image"):
        classes.append("hasimg")
    return f"""
      <li class="{' '.join(classes)}" data-price="{int(it['price'] or 0)}">
        <div class="thumb">{img}</div>
        <div class="cbody">
          {chips_html}
          <p class="cname">{escape(it['name'])}</p>
          <p class="cmeta"><span class="price">{yen(it['price'])}<i>円</i></span>{ago_html}</p>
          <p class="cshop">{escape(it['shop'])}</p>
          <div class="acts">
            <a class="cta" href="{escape(it['url'], quote=True)}" target="_blank" rel="nofollow sponsored noopener">予約ページへ</a>
            {amazon_link(it['name'])}
          </div>
        </div>
      </li>"""


def render_category(g, active):
    n = g["new_count"]
    rows = "\n".join(render_item(it) for it in g["items"])
    pid = re.sub(r"\W", "", g["name"])
    desc = CATEGORY_DESCRIPTIONS.get(g["name"], "予約開始・再販・新着販売の動きを確認できます。価格や在庫状況はリンク先で必ず確認してください。")
    return f"""
  <section class="panel{' active' if active else ''}" id="panel-{pid}" role="tabpanel">
    <header class="phead">
      <h2>{g['icon']} {escape(g['name'])}</h2>
      <p class="pmeta">直近24時間の新着 <b>{n}</b>件 ・ {len(g['items'])}件を監視中</p>
      <p class="pdesc">{escape(desc)}</p>
    </header>
    <ol class="cards">{rows}
    </ol>
    <p class="pnote">NEW = 直近24時間で初めてレーダーに映った商品。再販・取扱店追加を含むことがあります。受付状況はリンク先でご確認ください。</p>
  </section>"""


def build_html(data, demo, single=None):
    """single=カテゴリ辞書 を渡すと、そのカテゴリ専用ページ(SEO用)を作る"""
    now = datetime.now(JST)
    updated = f"{now.hour:02d}:{now.minute:02d}"
    updated_full = f"{now.year}年{now.month}月{now.day}日 {updated}"
    data_use = [single] if single else data
    total_new = sum(g["new_count"] for g in data_use)
    prefix = "../" if single else ""

    if single:
        page_title = f"{single['name']}の予約開始速報・新着まとめ|{SITE_NAME}"
        page_desc = (f"{single['name']}の予約開始情報を15分ごとに自動更新。直近24時間の新着予約を"
                     f"検知して速報します。受付中の予約一覧・発売時期つき。")
        page_url = f"{SITE_URL}{single['slug']}/" if SITE_URL else ""
        tabs = (f'      <a class="pill plink" href="{prefix}">🏠 すべて</a>\n'
                f'      <a class="pill plink" href="{prefix}trend/">🔥 急上昇</a>\n'
                f'      <a class="pill plink" href="{prefix}calendar/">📅 発売カレンダー</a>\n'
                f'      <a class="pill plink" href="{prefix}released/">✅ 発売済み</a>\n'
                + "\n".join(
            f'      <a class="pill plink{" on" if g["slug"] == single["slug"] else ""}" '
            f'href="{prefix}{g["slug"]}/">{g["icon"]} {escape(g["name"])}</a>'
            for g in data))
    else:
        page_title = f"{SITE_NAME}|{SITE_TAGLINE}"
        page_desc = SITE_DESCRIPTION
        page_url = SITE_URL
        tabs = (f'      <button class="pill on" role="tab" data-target="panel-feed">'
                f'🆕 新着フィード{f"<b class=cnt>{total_new}</b>" if total_new else ""}</button>\n'
                '      <a class="pill plink" href="trend/">🔥 急上昇</a>\n'
                '      <a class="pill plink" href="calendar/">📅 発売カレンダー</a>\n'
                '      <a class="pill plink" href="released/">✅ 発売済み</a>\n'
                + "\n".join(
            f'      <button class="pill" role="tab" '
            f'data-target="panel-{re.sub(r"\W", "", g["name"])}">'
            f'{g["icon"]} {escape(g["name"])}{f"<b class=cnt>{g['new_count']}</b>" if g["new_count"] else ""}</button>'
            for g in data))

    og = (f'<meta property="og:title" content="{escape(page_title, quote=True)}">\n'
          f'<meta property="og:description" content="{escape(page_desc, quote=True)}">\n'
          f'<meta property="og:type" content="website">\n'
          f'<meta property="og:site_name" content="{escape(SITE_NAME, quote=True)}">\n'
          + (f'<meta property="og:url" content="{escape(page_url, quote=True)}">\n' if page_url else "")
          + (f'<meta property="og:image" content="{escape(SITE_URL + "og-image.svg", quote=True)}">\n' if SITE_URL else "")
          + '<meta name="twitter:card" content="summary">')
    jsonld_items = [
        {"@type": "ListItem", "position": i + 1, "name": it["name"], "url": it["url"]}
        for i, it in enumerate(data_use[0]["items"][:10])
    ]
    jsonld = ('<script type="application/ld+json">'
              + json.dumps({"@context": "https://schema.org", "@type": "ItemList",
                            "name": page_title, "itemListElement": jsonld_items},
                           ensure_ascii=False)
              + "</script>")
    catlinks = (f'<p><a href="{prefix}privacy/">プライバシーポリシー</a></p>'
                '<p><strong>ページ一覧:</strong> '
                + f'<a href="{prefix}trend/">🔥急上昇トレンド</a> / '
                + f'<a href="{prefix}calendar/">📅発売カレンダー</a> / '
                + f'<a href="{prefix}released/">✅発売済みまとめ</a> / '
                + " / ".join(f'<a href="{prefix}{g["slug"]}/">{escape(g["name"])}</a>' for g in data)
                + "</p>")

    if single:
        panels = render_category(single, True)
    else:
        # 新着フィード: 全カテゴリのNEWを新しい順にマージ(Yahoo!ニュース型)
        feed_new = sorted(((it, g) for g in data for it in g["items"] if it["is_new"]),
                          key=lambda x: x[0]["first_seen"], reverse=True)[:30]
        if feed_new:
            feed_rows = "\n".join(render_item(it, g) for it, g in feed_new)
            feed_body = f'<ol class="cards">{feed_rows}\n    </ol>'
        else:
            feed_body = ('<div class="emptyfeed"><p class="ef-t">直近24時間の新着はまだありません</p>'
                         '<p class="ef-d">15分ごとに自動でチェックしています。受付中の予約は上のカテゴリから見られます。</p></div>')
        feed_panel = f"""
  <section class="panel active" id="panel-feed" role="tabpanel">
    <header class="phead">
      <h2>🆕 新着フィード</h2>
      <p class="pmeta">全カテゴリの直近24時間の新着を、見つけた順(新しい順)に表示</p>
    </header>
    {feed_body}
  </section>"""
        panels = feed_panel + "\n".join(render_category(g, False) for g in data)
    demo_note = ('<div class="demo-note">⚠ デモデータ表示中です。説明書の手順で楽天APIキーを設定すると本物の予約情報に切り替わります。</div>'
                 if demo else "")
    canonical = f'<link rel="canonical" href="{escape(page_url, quote=True)}">' if page_url else ""

    # Google AdSense(自動広告)。Secretに ADSENSE_CLIENT(ca-pub-…)を設定すると有効化
    ads_client = os.environ.get("ADSENSE_CLIENT", "").strip()
    adsense = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
               f'?client={escape(ads_client, quote=True)}" crossorigin="anonymous"></script>') if ads_client else ""

    cfg = {
        "yahooAppId": os.environ.get("YAHOO_APP_ID", "").strip(),
        "amazonTag": AMAZON_TAG,
        "dataUrl": f"{prefix}data.json",
        "searchApiUrl": os.environ.get("SEARCH_API_URL", "").strip(),
    }
    search_js = ('<script id="cross-search-script">'
                 + SEARCH_JS.replace("__SEARCH_CONFIG__", json.dumps(cfg, ensure_ascii=False))
                 + "</script>")
    vc_pid = os.environ.get("VC_PID", "").strip()
    linkswitch = (f'<script>var vc_pid = "{escape(vc_pid, quote=True)}";</script>\n'
                  '<script src="//aml.valuecommerce.com/vcdal.js" async></script>') if vc_pid else ""
    contact_links = []
    if X_ACCOUNT_URL:
        contact_links.append(f'<a href="{escape(X_ACCOUNT_URL, quote=True)}" target="_blank" rel="noopener">Xアカウント</a>')
    if CONTACT_URL:
        contact_links.append(f'<a href="{escape(CONTACT_URL, quote=True)}" target="_blank" rel="noopener">問い合わせ</a>')
    contact_html = " / ".join(contact_links) if contact_links else "問い合わせ先は準備中です"

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(page_title)}</title>
<meta name="description" content="{escape(page_desc, quote=True)}">
{canonical}
<link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
{og}
{jsonld}
{adsense}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Murecho:wght@700;900&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {{
  --paper: #F5F6F8;
  --card: #FFFFFF;
  --ink: #14181F;
  --muted: #707888;
  --rule: #E7E9EF;
  --green: #0BA678;       /* レーダーグリーン: 生存信号(LIVE・鮮度・選択中) */
  --green-bg: #E3F5EE;
  --new: #E5304F;
  --new-bg: #FDEBEF;
  --hot: #E8590C;
  --hot-bg: #FFF0E3;
  --marker: #FFE066;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{
  font-family: "Noto Sans JP", sans-serif;
  background: var(--paper); color: var(--ink);
  line-height: 1.65; -webkit-font-smoothing: antialiased;
  font-feature-settings: "palt";
}}
h1, h2, .brand, .price, .cnt {{ font-family: "Murecho", "Noto Sans JP", sans-serif; }}

/* ===== アプリバー ===== */
.appbar {{ background: var(--card); border-bottom: 1px solid var(--rule); padding: 14px 16px 12px; }}
.appbar-in {{ max-width: 680px; margin: 0 auto; }}
.brandrow {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; }}
.brand {{ font-size: 21px; font-weight: 900; letter-spacing: 0.01em; }}
.brand a {{ color: inherit; text-decoration: none; }}
.live {{ display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 700; color: var(--green); white-space: nowrap;
  font-variant-numeric: tabular-nums; }}
.pulse {{ width: 8px; height: 8px; border-radius: 50%; background: var(--green); position: relative; }}
.pulse::after {{ content: ""; position: absolute; inset: -4px; border-radius: 50%;
  border: 2px solid var(--green); opacity: 0; animation: ping 2.4s ease-out infinite; }}
@keyframes ping {{ 0% {{ transform: scale(0.4); opacity: 0.7; }} 70%, 100% {{ transform: scale(1); opacity: 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .pulse::after {{ animation: none; }} }}
.tag {{ max-width: 680px; margin: 3px auto 0; font-size: 12px; color: var(--muted); }}
.ad-label {{ font-size: 10.5px; color: var(--muted); text-align: center;
  padding: 6px 12px 0; }}
.demo-note {{ max-width: 680px; margin: 12px auto 0; padding: 10px 14px;
  background: #FFF6DB; border: 1px solid #E8C84A; border-radius: 12px;
  font-size: 12.5px; font-weight: 700; }}

/* ===== ピルレール(カテゴリ+新着数) ===== */
.pills {{ position: sticky; top: 0; z-index: 20;
  background: color-mix(in srgb, var(--paper) 88%, transparent);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  display: flex; gap: 8px; overflow-x: auto; padding: 10px 16px 12px;
  scrollbar-width: thin; scrollbar-color: #AEB6C4 transparent; box-shadow: 0 1px 0 var(--rule);
  touch-action: pan-x; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; }}
.pills::-webkit-scrollbar {{ height: 8px; }}
.pills::-webkit-scrollbar-track {{ background: transparent; }}
.pills::-webkit-scrollbar-thumb {{ background: #AEB6C4; border-radius: 999px; border: 2px solid transparent; background-clip: content-box; }}
.pills::-webkit-scrollbar-thumb:hover {{ background: #7D8796; background-clip: content-box; }}
.pill {{ flex: 0 0 auto; display: inline-flex; align-items: center; gap: 5px;
  font: inherit; font-size: 13px; font-weight: 700; color: var(--ink);
  background: var(--card); border: 1px solid var(--rule); border-radius: 999px;
  padding: 8px 14px; cursor: pointer; text-decoration: none; white-space: nowrap; }}
.pill.on {{ background: var(--ink); border-color: var(--ink); color: #fff; }}
.pill:focus-visible {{ outline: 3px solid var(--green); outline-offset: 2px; }}
.cnt {{ background: var(--new); color: #fff; font-size: 11px; font-weight: 900;
  min-width: 18px; text-align: center; border-radius: 999px; padding: 1px 6px; }}
.pill.on .cnt {{ background: #fff; color: var(--new); }}

/* ===== ツールバー ===== */
.toolbar {{ max-width: 680px; margin: 0 auto; padding: 12px 16px 0;
  display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }}
.sum {{ font-size: 13px; color: var(--muted); }}
.sum b {{ font-family: "Murecho", sans-serif; font-size: 17px; color: var(--ink); margin: 0 2px; }}
.sum b.haspos {{ color: var(--new); }}
.listtools {{ display: flex; align-items: center; gap: 8px 12px; flex-wrap: wrap; justify-content: flex-end; }}
.onlynew, .toolcheck {{ display: inline-flex; align-items: center; gap: 6px;
  font-size: 12.5px; font-weight: 700; cursor: pointer; color: var(--ink); }}
.onlynew input, .toolcheck input {{ width: 16px; height: 16px; accent-color: var(--green); }}
.pricefilter {{ display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; color: var(--ink); }}
.pricefilter input {{ width: 76px; font: inherit; font-size: 12px; padding: 5px 7px;
  border: 1px solid var(--rule); border-radius: 7px; background: var(--card); color: var(--ink); }}
.toolbtn {{ font: inherit; font-size: 12px; font-weight: 700; color: var(--muted);
  background: var(--card); border: 1px solid var(--rule); border-radius: 999px; padding: 6px 10px; cursor: pointer; }}
body.only-new .card:not(.isnew) {{ display: none; }}
body.only-hot .card:not(.ishot) {{ display: none; }}
body.only-image .card:not(.hasimg) {{ display: none; }}
.card.is-filtered {{ display: none !important; }}
.filter-empty {{ display: none; padding: 16px; text-align: center; font-size: 12px; color: var(--muted);
  background: var(--card); border: 1px dashed var(--rule); border-radius: 16px; }}
.filter-empty.show {{ display: block; }}

/* ===== パネル ===== */
main {{ max-width: 680px; margin: 0 auto; padding: 6px 16px 48px; }}
.panel {{ display: none; }}
.panel.active {{ display: block; }}
.phead {{ padding: 14px 2px 10px; }}
.phead h2 {{ font-size: 18px; font-weight: 900; }}
.pmeta {{ font-size: 12px; color: var(--muted); margin-top: 1px; }}
.pmeta b {{ color: var(--new); }}
.pdesc {{ font-size: 12.5px; color: var(--muted); margin-top: 6px; }}
.pnote {{ font-size: 11px; color: var(--muted); margin: 10px 2px 0; }}

/* ===== 商品カード ===== */
.cards {{ list-style: none; display: flex; flex-direction: column; gap: 10px; }}
.card {{ display: grid; grid-template-columns: 84px 1fr; gap: 12px;
  background: var(--card); border: 1px solid var(--rule); border-radius: 16px;
  padding: 14px; box-shadow: 0 1px 2px rgba(20, 24, 31, 0.04); }}
.card.isnew {{ border-color: color-mix(in srgb, var(--new) 35%, var(--rule));
  box-shadow: inset 3px 0 0 var(--new), 0 1px 2px rgba(20, 24, 31, 0.04); }}
.thumb img {{ width: 84px; height: 84px; object-fit: contain;
  border: 1px solid var(--rule); border-radius: 12px; background: #fff; }}
.noimg {{ width: 84px; height: 84px; display: grid; place-items: center; text-align: center;
  border: 1px dashed var(--rule); border-radius: 12px; color: var(--muted);
  font-size: 10px; line-height: 1.4; }}
.cchips {{ display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 5px; }}
.cchips span {{ font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }}
.chip-new {{ background: var(--new); color: #fff; letter-spacing: 0.04em; }}
.chip-hot {{ background: var(--hot-bg); color: var(--hot); }}
.chip-rel {{ background: var(--green-bg); color: var(--green); }}
.chip-cat {{ background: var(--paper); border: 1px solid var(--rule); color: var(--muted); }}
.emptyfeed {{ background: var(--card); border: 1px dashed var(--rule); border-radius: 16px;
  padding: 26px 18px; text-align: center; }}
.ef-t {{ font-size: 14px; font-weight: 700; }}
.ef-d {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
body.only-new .cards:not(:has(.card.isnew))::after {{
  content: "このカテゴリに直近24時間の新着はありません";
  display: block; padding: 16px; text-align: center; font-size: 12px; color: var(--muted);
  background: var(--card); border: 1px dashed var(--rule); border-radius: 16px; }}
.cname {{ font-size: 13px; font-weight: 500; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.cmeta {{ display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-top: 6px; }}
.price {{ font-size: 18px; font-weight: 900; font-variant-numeric: tabular-nums; }}
.price i {{ font-style: normal; font-size: 11px; font-weight: 700; color: var(--muted); margin-left: 1px; }}
.fresh {{ font-size: 11.5px; font-weight: 700; color: var(--green);
  font-variant-numeric: tabular-nums; }}
.seen {{ font-size: 11px; color: var(--muted); }}
.cshop {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
.acts {{ display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }}
.cta {{ background: var(--ink); color: #fff; font-size: 12.5px; font-weight: 700;
  text-decoration: none; padding: 9px 18px; border-radius: 999px; }}
.card.isnew .cta {{ background: var(--new); }}
.cta.amzn {{ background: transparent; color: var(--ink);
  border: 1px solid var(--rule); padding: 8px 14px; font-size: 11.5px; }}
.cta:focus-visible {{ outline: 3px solid var(--green); outline-offset: 2px; }}

/* ===== フッター・戻る ===== */
footer {{ border-top: 1px solid var(--rule); background: var(--card);
  padding: 24px 16px 36px; font-size: 12px; color: var(--muted); }}
.foot-inner {{ max-width: 680px; margin: 0 auto; display: flex; flex-direction: column; gap: 8px; }}
.foot-inner strong {{ color: var(--ink); }}
.foot-inner a {{ color: var(--green); }}
#totop {{ position: fixed; right: 16px; bottom: 20px; z-index: 40;
  width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--rule);
  background: var(--card); color: var(--ink); font-size: 18px; font-weight: 700;
  cursor: pointer; box-shadow: 0 4px 14px rgba(20, 24, 31, 0.16); display: none; }}
#totop.show {{ display: block; }}

/* ===== PC幅: 商品カード一覧をグリッド表示に(スマホは縦リストのまま) ===== */
@media (min-width: 860px) {{
  .appbar-in, .tag, .demo-note, main, .toolbar, .foot-inner {{ max-width: 1100px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 14px; }}
  .card {{ grid-template-columns: 1fr; }}
  .thumb img, .noimg {{ width: 100%; height: 160px; }}
  .cname {{ -webkit-line-clamp: 3; }}
  body.only-new .cards:not(:has(.card.isnew))::after {{ grid-column: 1 / -1; }}
}}

/* ===== ダークモード ===== */
@media (prefers-color-scheme: dark) {{
  :root {{ --paper: #0E1117; --card: #171B24; --ink: #ECEEF3; --muted: #98A0B0;
    --rule: #272C38; --green: #2EC592; --green-bg: #15302A;
    --new: #FF5D77; --new-bg: #3A1622; --hot: #FFA94D; --hot-bg: #3A2710;
    --marker: #5C4D12; }}
  .thumb img, .noimg {{ background: #0B0E14; }}
  .demo-note {{ background: #332B0E; border-color: #8A7A1E; color: #F2E7AE; }}
  .pill.on {{ background: var(--green); border-color: var(--green); color: #08110D; }}
  .pill.on .cnt {{ background: #08110D; color: var(--new); }}
  .cta {{ color: #0E1117; background: #ECEEF3; }}
  .card.isnew .cta {{ background: var(--new); color: #1A0B10; }}
  .cta.amzn {{ background: transparent; color: var(--ink); }}
}}
{SEARCH_CSS}
</style>
</head>
<body>
<header class="appbar">
  <div class="appbar-in">
    <div class="brandrow">
      <h1 class="brand"><a href="{prefix if single else './'}">予約開始レーダー</a></h1>
      <span class="live"><i class="pulse"></i>{updated} 更新</span>
    </div>
  </div>
  <p class="tag">{escape(SITE_TAGLINE)}。15分ごとに新しい予約だけを検知します。</p>
</header>
<p class="ad-label">本ページはプロモーション(楽天・Yahoo!ショッピング等のアフィリエイト広告)を含みます</p>
{demo_note}
{SEARCH_HTML}
<nav class="pills" role="tablist">
{tabs}
</nav>
<div class="toolbar">
  <span class="sum">直近24時間の新着 <b class="{'haspos' if total_new else ''}">{total_new}</b> 件</span>
  <div class="listtools">
    <label class="onlynew"><input type="checkbox" id="onlynew"> 新着だけ</label>
    <label class="toolcheck"><input type="checkbox" id="sortcheap"> 安い順</label>
    <label class="toolcheck"><input type="checkbox" id="onlyhot"> 注目だけ</label>
    <label class="toolcheck"><input type="checkbox" id="onlyimage"> 画像あり</label>
    <label class="pricefilter">価格 <input type="number" id="minprice" min="0" step="100" placeholder="下限"> - <input type="number" id="maxprice" min="0" step="100" placeholder="上限"></label>
    <button type="button" class="toolbtn" id="resetfilters">リセット</button>
  </div>
</div>

<main>
{panels}
</main>

<footer>
  <div class="foot-inner">
    <p><strong>{escape(SITE_NAME)}について</strong></p>
    <p>楽天市場の各ホビーカテゴリを15分ごとに自動巡回し、直近24時間で初めてレーダーに映った商品を「NEW」として表示しています。検知の仕組み上、再販・価格改定・新店舗の取り扱い開始もNEWに含まれることがあります。</p>
    <p>予約の受付状況・価格・特典は変動が激しいため、必ずリンク先の最新情報をご確認ください。本サイトは定価での予約機会を見つけるための情報サイトであり、転売を推奨するものではありません。</p>
    <p>当サイトは楽天アフィリエイト等に参加しており、リンク経由の購入により紹介料を得ることがあります。</p>
    <p><strong>運営者:</strong> {escape(OPERATOR_NAME)} / {contact_html}</p>
    <p>掲載内容に誤りがある場合や削除依頼がある場合は、上記連絡先からお知らせください。</p>
    {catlinks}
    <p>最終更新: {updated_full}</p>
  </div>
</footer>

<button id="totop" aria-label="ページの先頭へ">↑</button>
<script>
document.querySelectorAll('.pill[data-target]').forEach(function (tab) {{
  tab.addEventListener('click', function () {{
    document.querySelectorAll('.pill[data-target]').forEach(function (t) {{ t.classList.remove('on'); }});
    document.querySelectorAll('.panel').forEach(function (p) {{ p.classList.remove('active'); }});
    tab.classList.add('on');
    document.getElementById(tab.dataset.target).classList.add('active');
    tab.scrollIntoView({{ inline: 'center', block: 'nearest', behavior: 'smooth' }});
    window.scrollTo({{ top: 0 }});
  }});
}});
var onlyNew = document.getElementById('onlynew');
var sortCheap = document.getElementById('sortcheap');
var onlyHot = document.getElementById('onlyhot');
var onlyImage = document.getElementById('onlyimage');
var minPrice = document.getElementById('minprice');
var maxPrice = document.getElementById('maxprice');
var resetFilters = document.getElementById('resetfilters');
document.querySelectorAll('.cards').forEach(function (list) {{
  Array.prototype.forEach.call(list.children, function (card, i) {{
    card.dataset.order = i;
  }});
}});
function applyListTools() {{
  document.body.classList.remove('only-new', 'only-hot', 'only-image');
  var min = minPrice && minPrice.value !== '' ? Number(minPrice.value) : null;
  var max = maxPrice && maxPrice.value !== '' ? Number(maxPrice.value) : null;
  document.querySelectorAll('.card').forEach(function (card) {{
    var price = Number(card.dataset.price || 0);
    var hide = (onlyNew && onlyNew.checked && !card.classList.contains('isnew')) ||
      (onlyHot && onlyHot.checked && !card.classList.contains('ishot')) ||
      (onlyImage && onlyImage.checked && !card.classList.contains('hasimg')) ||
      (min !== null && price < min) || (max !== null && price > max);
    card.classList.toggle('is-filtered', hide);
  }});
  document.querySelectorAll('.cards').forEach(function (list) {{
    var cards = Array.prototype.slice.call(list.children);
    cards.sort(function (a, b) {{
      if (sortCheap && sortCheap.checked) {{
        return Number(a.dataset.price || 0) - Number(b.dataset.price || 0);
      }}
      return Number(a.dataset.order || 0) - Number(b.dataset.order || 0);
    }});
    cards.forEach(function (card) {{ list.appendChild(card); }});
    var empty = list.nextElementSibling && list.nextElementSibling.classList.contains('filter-empty')
      ? list.nextElementSibling : null;
    if (!empty) {{
      empty = document.createElement('p');
      empty.className = 'filter-empty';
      empty.textContent = '条件に合う商品がありません。';
      list.insertAdjacentElement('afterend', empty);
    }}
    var visible = cards.some(function (card) {{ return !card.classList.contains('is-filtered'); }});
    empty.classList.toggle('show', !visible && cards.length > 0);
  }});
}}
if (onlyNew) {{
  [onlyNew, sortCheap, onlyHot, onlyImage, minPrice, maxPrice].forEach(function (el) {{
    if (!el) return;
    el.addEventListener(el.type === 'number' ? 'input' : 'change', applyListTools);
  }});
  resetFilters.addEventListener('click', function () {{
    [onlyNew, sortCheap, onlyHot, onlyImage].forEach(function (el) {{ if (el) el.checked = false; }});
    if (minPrice) minPrice.value = '';
    if (maxPrice) maxPrice.value = '';
    applyListTools();
  }});
}}
var totop = document.getElementById('totop');
window.addEventListener('scroll', function () {{
  totop.classList.toggle('show', window.scrollY > 600);
}}, {{ passive: true }});
totop.addEventListener('click', function () {{ window.scrollTo({{ top: 0, behavior: 'smooth' }}); }});
</script>
{search_js}
{linkswitch}
</body>
</html>
"""


def write_privacy_page(out_dir):
    """プライバシーポリシー(広告掲載・AdSense審査の必須要件)"""
    now = datetime.now(JST)
    body = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>プライバシーポリシー|{escape(SITE_NAME)}</title>
<meta name="robots" content="noindex, follow">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {{ --paper:#F5F6F8; --card:#fff; --ink:#14181F; --muted:#707888; --rule:#E7E9EF; --green:#0BA678; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --paper:#0E1117; --card:#171B24; --ink:#ECEEF3; --muted:#98A0B0; --rule:#272C38; --green:#2EC592; }} }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"Noto Sans JP",sans-serif; background:var(--paper); color:var(--ink); line-height:1.8; }}
main {{ max-width:680px; margin:0 auto; padding:28px 18px 60px; }}
h1 {{ font-size:20px; margin-bottom:18px; }}
h2 {{ font-size:15px; margin:22px 0 6px; padding-left:10px; border-left:4px solid var(--green); }}
p {{ font-size:13px; margin-bottom:8px; }}
a {{ color:var(--green); }}
.back {{ display:inline-block; margin-bottom:18px; font-size:13px; }}
</style>
</head>
<body>
<main>
<a class="back" href="../">← {escape(SITE_NAME)} トップへ戻る</a>
<h1>プライバシーポリシー</h1>
<h2>広告の配信について</h2>
<p>当サイトは第三者配信の広告サービス(Google AdSense)を利用する場合があります。広告配信事業者は、ユーザーの興味に応じた広告を表示するためにCookieを使用することがあります。Cookieを無効にする設定およびGoogle AdSenseに関する詳細は、Googleの「広告 ― ポリシーと規約」をご確認ください。パーソナライズ広告は、Googleの広告設定ページで無効にできます。</p>
<h2>アフィリエイトプログラムについて</h2>
<p>当サイトは、楽天アフィリエイト、バリューコマース、Amazonアソシエイト・プログラム等のアフィリエイトプログラムに参加しています。商品リンクを経由して購入が行われた場合、当サイトに紹介料が支払われることがあります。価格・在庫・特典等の最新情報は、必ずリンク先の販売ページでご確認ください。</p>
<h2>アクセス解析について</h2>
<p>当サイトは、サービス向上のためにアクセス解析ツールを利用する場合があります。解析ツールはトラフィックデータの収集のためにCookieを使用することがありますが、このデータは匿名で収集されており、個人を特定するものではありません。</p>
<h2>免責事項</h2>
<p>当サイトに掲載する情報は自動収集・自動解析によるもので、正確性・完全性を保証するものではありません。当サイトの利用によって生じた損害について、当サイトは一切の責任を負いません。商品の予約・購入は各販売店の規約に従ってください。</p>
<h2>本ポリシーの変更</h2>
<p>本ポリシーの内容は、法令の変更やサービス内容の変更に応じて、予告なく改定されることがあります。</p>
<p>制定日: {now.year}年{now.month}月{now.day}日</p>
</main>
</body>
</html>
"""
    page_dir = os.path.join(out_dir, "privacy")
    os.makedirs(page_dir, exist_ok=True)
    with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(body)


def write_brand_assets(out_dir):
    favicon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#14181F"/>
<circle cx="32" cy="32" r="21" fill="none" stroke="#0BA678" stroke-width="5"/>
<path d="M32 32 48 22" stroke="#FFE066" stroke-width="5" stroke-linecap="round"/>
<circle cx="32" cy="32" r="5" fill="#E5304F"/>
<path d="M14 44h36" stroke="#fff" stroke-width="4" stroke-linecap="round" opacity=".9"/>
</svg>
"""
    og = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#F5F6F8"/>
<rect x="72" y="70" width="1056" height="490" rx="32" fill="#FFFFFF" stroke="#E7E9EF" stroke-width="3"/>
<circle cx="190" cy="198" r="72" fill="#E3F5EE"/>
<circle cx="190" cy="198" r="48" fill="none" stroke="#0BA678" stroke-width="12"/>
<path d="M190 198 232 170" stroke="#E5304F" stroke-width="12" stroke-linecap="round"/>
<circle cx="190" cy="198" r="12" fill="#14181F"/>
<text x="300" y="205" font-family="Arial, 'Noto Sans JP', sans-serif" font-size="76" font-weight="800" fill="#14181F">{escape(SITE_NAME)}</text>
<text x="304" y="282" font-family="Arial, 'Noto Sans JP', sans-serif" font-size="34" font-weight="700" fill="#0BA678">ホビーの予約開始を毎日自動キャッチ</text>
<text x="304" y="354" font-family="Arial, 'Noto Sans JP', sans-serif" font-size="28" fill="#707888">ポケカ / ガンプラ / フィギュア / ゲーム / グッズ</text>
<rect x="304" y="414" width="380" height="62" rx="31" fill="#14181F"/>
<text x="342" y="456" font-family="Arial, 'Noto Sans JP', sans-serif" font-size="25" font-weight="700" fill="#FFFFFF">新着予約をすばやく確認</text>
</svg>
"""
    with open(os.path.join(out_dir, "favicon.svg"), "w", encoding="utf-8") as f:
        f.write(favicon)
    with open(os.path.join(out_dir, "og-image.svg"), "w", encoding="utf-8") as f:
        f.write(og)


# ============================================================
# メイン
# ============================================================

def main():
    data, seen, demo = collect_data()
    if not data:
        print("エラー: 商品を1件も取得できませんでした。", file=sys.stderr)
        sys.exit(1)

    # APIキー未設定(デモ)時は本番の docs/ を上書きしないよう別フォルダに出力する
    out_dir = os.path.join(HERE, "docs_preview" if demo else "docs")
    if demo:
        print(f"[情報] デモデータのため本番の docs/ には書き込まず {out_dir} に出力します。", file=sys.stderr)
    os.makedirs(out_dir, exist_ok=True)

    if not demo:  # デモデータで記録を汚さない
        with open(os.path.join(out_dir, "seen.json"), "w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False)

    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_html(data, demo))

    # カテゴリ別ページ(「◯◯ 予約」系の検索流入を受けるSEOページ)
    for g in data:
        page_dir = os.path.join(out_dir, g["slug"])
        os.makedirs(page_dir, exist_ok=True)
        with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_html(data, demo, single=g))

    # RSSフィード(新着予約の蓄積。リーダー登録・通知ツール連携用)
    feed_path = os.path.join(out_dir, "feed_items.json")
    feed_items = []
    if os.path.exists(feed_path):
        try:
            with open(feed_path, encoding="utf-8") as f:
                feed_items = json.load(f)
        except Exception:
            pass
    if not demo:
        today_iso = datetime.now(JST).strftime("%a, %d %b %Y 06:00:00 +0900")
        existing = {x["url"] for x in feed_items}
        for g in data:
            for it in g["items"]:
                if it["is_new"] and it["url"] not in existing:
                    feed_items.insert(0, {"name": it["name"], "url": it["url"],
                                          "price": it["price"], "cat": g["name"],
                                          "pub": today_iso})
        feed_items = feed_items[:60]
        with open(feed_path, "w", encoding="utf-8") as f:
            json.dump(feed_items, f, ensure_ascii=False)
    rss_entries = "\n".join(
        f"<item><title>{escape(x['name'])}({x['price']:,}円/{escape(x['cat'])})</title>"
        f"<link>{escape(x['url'])}</link><guid isPermaLink=\"false\">{escape(x['url'])}</guid>"
        f"<pubDate>{x['pub']}</pubDate></item>"
        for x in feed_items)
    rss = (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
           f"<title>{escape(SITE_NAME)} 新着予約</title>"
           f"<link>{escape(SITE_URL) or 'https://example.com/'}</link>"
           f"<description>{escape(SITE_DESCRIPTION)}</description>\n{rss_entries}\n</channel></rss>")
    with open(os.path.join(out_dir, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(rss)

    # sitemap.xml と robots.txt(SITE_URLを設定すると検索エンジンに全ページを案内できる)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if SITE_URL:
        urls = ([SITE_URL, f"{SITE_URL}trend/", f"{SITE_URL}calendar/", f"{SITE_URL}released/", f"{SITE_URL}privacy/"]
                + [f"{SITE_URL}{g['slug']}/" for g in data])
        sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
              + "\n".join(f"<url><loc>{escape(u)}</loc><lastmod>{today}</lastmod>"
                           f"<changefreq>daily</changefreq></url>" for u in urls)
              + "\n</urlset>")
        with open(os.path.join(out_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write(sm)
    with open(os.path.join(out_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n"
                + (f"Sitemap: {SITE_URL}sitemap.xml\n" if SITE_URL else ""))

    # プライバシーポリシー(AdSense審査・広告掲載に必須)と ads.txt
    write_brand_assets(out_dir)
    write_privacy_page(out_dir)
    ads_client = os.environ.get("ADSENSE_CLIENT", "").strip()
    if ads_client:
        pub_id = ads_client.replace("ca-", "")
        with open(os.path.join(out_dir, "ads.txt"), "w", encoding="utf-8") as f:
            f.write(f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n")

    # 発売日カレンダー。失敗してもサイト本体は止めない
    try:
        calendar_page.build_calendar_page(out_dir, data, SITE_NAME, SITE_URL, demo)
    except Exception as e:
        print(f"[警告] カレンダー生成に失敗(本体には影響なし): {e}", file=sys.stderr)

    # 発売済み・販売中まとめページ。失敗してもサイト本体は止めない
    try:
        import released_page
        released_page.build_released_page(out_dir, data, SITE_NAME, SITE_URL, demo)
    except Exception as e:
        print(f"[警告] 発売済みページ生成に失敗(本体には影響なし): {e}", file=sys.stderr)

    # トレンドページ(自前頻度解析+Google Trends)。失敗してもサイト本体は止めない
    try:
        import trends
        trends.build_trend_page(
            out_dir, CATEGORIES, SITE_NAME, SITE_URL, demo,
            app_id=os.environ.get("RAKUTEN_APP_ID", "").strip(),
            affiliate_id=os.environ.get("RAKUTEN_AFFILIATE_ID", "").strip(),
            full=is_full_run())
    except Exception as e:
        print(f"[警告] トレンドページ生成に失敗(本体には影響なし): {e}", file=sys.stderr)

    # SNS自動投稿(post_sns.py)用データ
    sns = {
        "generated_at": datetime.now(JST).isoformat(),
        "demo": demo,
        "site_name": SITE_NAME,
        "site_url": SITE_URL,
        "genres": [
            {
                "name": g["name"], "icon": g["icon"], "tag": g.get("tag", ""),
                "new_count": g["new_count"],
                "items": [
                    {"name": it["name"], "price": it["price"], "url": it["url"],
                     "release": it["release"], "is_new": it["is_new"],
                     "image": it.get("image", ""), "shop": it.get("shop", ""),
                     "hot": it.get("hot", False)}
                    for it in g["items"]
                ],
            }
            for g in data
        ],
    }
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(sns, f, ensure_ascii=False, indent=1)

    total_new = sum(g["new_count"] for g in data)
    print(f"完了: {'デモデータ' if demo else '楽天API(本番)'} / 本日の新着 {total_new}件")


if __name__ == "__main__":
    main()
