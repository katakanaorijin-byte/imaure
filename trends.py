# -*- coding: utf-8 -*-
"""
トレンド検知エンジン(予約開始レーダー用)

2つの情報源からトレンドページ(docs/trend/index.html)を作ります:
  ① 自前トレンド: このサイト自身が記録してきた新着予約(feed_items.json)を頻度解析し、
     「直近7日でいちばん予約が集中しているワード」を抽出 … 常に動く
  ② 世間トレンド: Google Trends の急上昇ワード(pytrends使用)を取得し、
     各ワードを楽天で検索して関連商品を表示 … 取得できない日は自動でスキップ

generate.py から呼ばれます。単体テストも可能:
  python trends.py  (デモ生成)
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta
from html import escape

from search_assets import SEARCH_CSS, SEARCH_HTML, SEARCH_JS

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
API_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"

# Google Trendsで「急上昇」を引き出すための種ワード(ホビー領域)
TREND_SEEDS = ["ポケカ", "ガンプラ", "フィギュア", "ワンピースカード"]

# 頻度解析で無視する一般語(商品名の飾り言葉)
STOPWORDS = {
    "予約", "送料無料", "特典", "付き", "セット", "限定", "限定版", "通常版", "新品",
    "BOX", "ボックス", "パック", "カートン", "シュリンク", "未開封", "国内正規品",
    "あす楽", "ポイント", "クーポン", "発売", "発送", "入荷", "予定", "より", "順次",
    "フィギュア", "プラモデル", "カード", "ゲーム", "グッズ", "ぬいぐるみ", "ソフト",
    "公式", "正規", "version", "ver", "edition", "the", "and", "for", "with",
}


# ============================================================
# ① 自前トレンド: 新着予約データの頻度解析
# ============================================================

def tokenize(name: str):
    """商品名から意味のありそうな語を取り出す(カタカナ連続・漢字連続・英数語)"""
    t = unicodedata.normalize("NFKC", name)  # 全角カッコ等はここで半角に揃う
    t = re.sub(r"【[^】]*】|\[[^\]]*\]|\([^)]*\)", " ", t)  # 飾りカッコを除去
    tokens = re.findall(r"[ァ-ヶー]{3,}|[一-龥]{2,}|[A-Za-z][A-Za-z0-9\.\-]{2,}", t)
    out = []
    for tk in tokens:
        tk = tk.strip("ー-.")
        if len(tk) < 2 or tk in STOPWORDS or tk.lower() in STOPWORDS:
            continue
        if re.fullmatch(r"\d+", tk):
            continue
        out.append(tk)
    return out


def own_trends(feed_items, days=7, top_n=12):
    """直近days日の新着予約から頻出ワードを抽出 → [(ワード, 回数, 例の商品), ...]"""
    cutoff = datetime.now(JST) - timedelta(days=days)
    counter = Counter()
    example = {}
    for x in feed_items:
        # pub形式: "Thu, 12 Jun 2026 06:00:00 +0900"
        try:
            d = datetime.strptime(x["pub"], "%a, %d %b %Y %H:%M:%S %z")
            if d < cutoff:
                continue
        except Exception:
            pass
        for tk in set(tokenize(x["name"])):
            counter[tk] += 1
            example.setdefault(tk, x)
    return [(w, c, example[w]) for w, c in counter.most_common(top_n) if c >= 2]


# ============================================================
# ②' ニュース・ネットの話題: RSS解析エンジン
# ============================================================

# 巡回するニュースフィード(取得に失敗したものは自動でスキップされます)
# URLが変わって動かなくなったら、ここを編集すればOK
NEWS_FEEDS = [
    ("4Gamer", "https://www.4gamer.net/rss/index.xml"),
    ("GAME Watch", "https://game.watch.impress.co.jp/data/rss/1.0/gmw/feed.rdf"),
    ("HOBBY Watch", "https://hobby.watch.impress.co.jp/data/rss/1.0/hbw/feed.rdf"),
    ("ファミ通", "https://www.famitsu.com/rss/famitsu_all.xml"),
    ("電撃ホビー", "https://hobby.dengeki.com/feed/"),
    ("はてブ アニメとゲーム", "https://b.hatena.ne.jp/hotentry/game.rss"),
]

# 「ホビー関連の見出し」と判定するためのヒント語
HOBBY_HINTS = [
    "予約", "発売", "抽選", "再販", "限定", "コラボ", "ポケモン", "ポケカ",
    "ガンダム", "ガンプラ", "フィギュア", "ねんどろいど", "figma", "一番くじ",
    "プラモ", "トミカ", "プラレール", "遊戯王", "ワンピース", "鬼滅", "呪術",
    "仮面ライダー", "戦隊", "プリキュア", "ウルトラマン", "Switch", "PS5",
    "トレカ", "カードゲーム", "ホビー", "グッズ", "ぬいぐるみ", "アニメ",
]

NEWS_STOP = STOPWORDS | {
    "発表", "公開", "開始", "登場", "紹介", "情報", "記事", "画像", "動画",
    "本日", "今日", "明日", "最新", "話題", "まとめ", "レビュー", "レポート",
    "インタビュー", "プレゼント", "キャンペーン", "ニュース", "更新", "配信",
}


def _parse_feed(xml_text: str, source: str):
    """RSS2 / RDF / Atom のどれでも見出しを取り出す"""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    out = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out
    # RSS2 と RDF の <item>(名前空間あり/なし両対応)
    items = [el for el in root.iter() if el.tag.split("}")[-1] in ("item", "entry")]
    for el in items:
        title, link, pub = "", "", None
        for child in el:
            tag = child.tag.split("}")[-1]
            if tag == "title":
                title = (child.text or "").strip()
            elif tag == "link":
                link = (child.text or "").strip() or child.attrib.get("href", "")
            elif tag in ("pubDate", "date", "updated", "published"):
                raw = (child.text or "").strip()
                try:
                    pub = parsedate_to_datetime(raw)
                except Exception:
                    try:
                        pub = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    except Exception:
                        pub = None
        if title:
            out.append({"title": title, "link": link, "source": source, "pub": pub})
    return out


def fetch_news(hours=48):
    """全フィードを巡回して、直近のホビー関連見出しを集める"""
    cutoff = datetime.now(JST) - timedelta(hours=hours)
    headlines, seen_titles = [], set()
    for source, url in NEWS_FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "yoyaku-radar-news/1.0"})
            with urllib.request.urlopen(req, timeout=15) as res:
                xml_text = res.read().decode("utf-8", errors="replace")
            entries = _parse_feed(xml_text, source)
            print(f"[ニュース] {source}: {len(entries)}件取得")
        except Exception as e:
            print(f"[ニュース] {source} 取得失敗(スキップ): {e}", file=sys.stderr)
            continue
        for e in entries:
            if e["pub"] is not None:
                try:
                    if e["pub"].astimezone(JST) < cutoff:
                        continue
                except Exception:
                    pass
            if e["title"] in seen_titles:
                continue
            seen_titles.add(e["title"])
            headlines.append(e)
        time.sleep(0.5)
    return headlines


def news_trends(headlines, top_words=10, top_heads=10):
    """見出し群から (話題ワード, ホビー関連ヘッドライン) を抽出"""
    hobby_heads = [h for h in headlines
                   if any(k.lower() in h["title"].lower() for k in HOBBY_HINTS)]
    counter = Counter()
    for h in hobby_heads:
        for tk in set(tokenize(h["title"])):
            if tk not in NEWS_STOP and tk.lower() not in NEWS_STOP:
                counter[tk] += 1
    words = [(w, c) for w, c in counter.most_common(top_words) if c >= 2]

    def sort_key(h):
        try:
            return h["pub"].astimezone(JST)
        except Exception:
            return datetime.now(JST)
    hobby_heads.sort(key=sort_key, reverse=True)
    return words, hobby_heads[:top_heads]


def _ago(pub):
    if pub is None:
        return ""
    try:
        delta = datetime.now(JST) - pub.astimezone(JST)
        hours = int(delta.total_seconds() // 3600)
        return "1時間以内" if hours < 1 else (f"{hours}時間前" if hours < 24 else f"{hours // 24}日前")
    except Exception:
        return ""


# ============================================================
# ② 世間トレンド: Google Trends 急上昇ワード(取れたらラッキー方式)
# ============================================================

def google_rising(max_terms=8):
    """pytrendsで種ワードの急上昇関連クエリを取得。失敗したら空リスト(サイトは止めない)"""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("[トレンド] pytrends未インストールのため世間トレンドはスキップ", file=sys.stderr)
        return []
    terms, seen = [], set()
    try:
        pt = TrendReq(hl="ja-JP", tz=-540, timeout=(10, 20))
        for seed in TREND_SEEDS:
            try:
                pt.build_payload([seed], timeframe="now 7-d", geo="JP")
                rq = pt.related_queries().get(seed, {})
                rising = rq.get("rising")
                if rising is None or rising.empty:
                    continue
                for q in list(rising["query"].head(3)):
                    q = str(q).strip()
                    if q and q not in seen and len(q) <= 30:
                        seen.add(q)
                        terms.append(q)
            except Exception as e:
                print(f"[トレンド] Google Trends {seed} 取得失敗: {e}", file=sys.stderr)
            time.sleep(2.5)  # 連続アクセスを避ける
            if len(terms) >= max_terms:
                break
    except Exception as e:
        print(f"[トレンド] Google Trends 全体エラー: {e}", file=sys.stderr)
    return terms[:max_terms]


def rakuten_top_items(app_id, affiliate_id, keyword, hits=3):
    """急上昇ワードに対応する商品を楽天で検索(1ワード=1リクエスト)"""
    params = {
        "applicationId": app_id, "format": "json",
        "keyword": keyword, "hits": hits, "availability": 1,
    }
    if affiliate_id:
        params["affiliateId"] = affiliate_id
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "yoyaku-radar-trends"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"[トレンド] 楽天検索失敗({keyword}): {e}", file=sys.stderr)
        return []
    items = []
    for e in data.get("Items", [])[:hits]:
        it = e.get("Item", e)
        image = ""
        if it.get("mediumImageUrls"):
            image = it["mediumImageUrls"][0].get("imageUrl", "").replace("?_ex=128x128", "?_ex=300x300")
        items.append({
            "name": it.get("itemName", ""), "price": int(it.get("itemPrice", 0) or 0),
            "url": it.get("affiliateUrl") or it.get("itemUrl", ""), "image": image,
            "shop": it.get("shopName", ""),
        })
    return items


# ============================================================
# トレンドページ生成
# ============================================================

def _item_row(it):
    img = (f'<img src="{escape(it["image"], quote=True)}" alt="" loading="lazy">'
           if it["image"] else '<div class="noimg">画像<br>なし</div>')
    return f"""
      <li class="row">
        <div class="thumb">{img}</div>
        <div class="meta">
          <p class="iname">{escape(it['name'])}</p>
          <p class="sub"><span class="price">{it['price']:,}<small>円</small></span></p>
          <p class="shop">{escape(it['shop'])}</p>
        </div>
        <a class="cta" href="{escape(it['url'], quote=True)}" target="_blank" rel="nofollow sponsored noopener">商品を見る</a>
      </li>"""


def build_trend_page(out_dir, categories, site_name, site_url, demo,
                     app_id="", affiliate_id="", full=True):
    now = datetime.now(JST)
    updated = f"{now.year}年{now.month}月{now.day}日"

    # ① 自前トレンド
    feed_path = os.path.join(out_dir, "feed_items.json")
    feed_items = []
    if os.path.exists(feed_path):
        try:
            with open(feed_path, encoding="utf-8") as f:
                feed_items = json.load(f)
        except Exception:
            pass
    if demo and not feed_items:
        feed_items = [
            {"name": f"【予約】メガリザードン 30th CELEBRATION BOX シュリンク付き", "url": "#",
             "price": 7200, "cat": "ポケモンカード", "pub": now.strftime("%a, %d %b %Y 06:00:00 +0900")}
        ] * 3 + [
            {"name": "【予約】HG ガンダム 新作キット 限定クリアカラー", "url": "#",
             "price": 2800, "cat": "ガンプラ", "pub": now.strftime("%a, %d %b %Y 06:00:00 +0900")}
        ] * 2
    own = own_trends(feed_items)

    # ②' ニュース・ネットの話題(RSS解析)
    if demo:
        now_pub = datetime.now(JST)
        demo_heads = [
            {"title": "「30th CELEBRATION」予約抽選が各店で開始 倍率は過去最高か", "link": "#", "source": "デモニュース", "pub": now_pub},
            {"title": "新作ガンプラ ジークアクス HGシリーズ 7月発売決定", "link": "#", "source": "デモニュース", "pub": now_pub},
            {"title": "ねんどろいど 人気キャラ再販決定 予約は明日から", "link": "#", "source": "デモニュース", "pub": now_pub},
        ]
        news_words, news_heads = news_trends(demo_heads * 2)
    else:
        news_words, news_heads = news_trends(fetch_news())
    news_count = len(news_heads)

    news_chips = "\n".join(
        f'<a class="chip" href="./?q={urllib.parse.quote(w)}">{escape(w)} <b>×{c}</b></a>'
        for w, c in news_words) or '<p class="empty">本日はニューストレンドを取得できませんでした(自動で再試行します)</p>'
    heads_html = "\n".join(
        f'<li class="nrow"><a href="{escape(h["link"], quote=True)}" target="_blank" rel="noopener">'
        f'{escape(h["title"])}</a><span class="nsrc">{escape(h["source"])}'
        f'{(" ・ " + _ago(h["pub"])) if _ago(h["pub"]) else ""}</span></li>'
        for h in news_heads) or '<li class="nrow"><span class="nsrc">取得できた見出しがありません</span></li>'

    # ② 世間トレンド(重い処理なのでフル便=1日3回のみ実行。軽量便はキャッシュ表示)
    cache_path = os.path.join(out_dir, "trend_cache.json")
    cache = {"rising": [], "blocks": []}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass

    if demo:
        rising = ["30th CELEBRATION", "メガリザードン"]
        block_data = [{"kw": kw, "items": []} for kw in rising]
    elif full:
        rising = google_rising()
        block_data = []
        for kw in rising:
            items = rakuten_top_items(app_id, affiliate_id, kw) if app_id else []
            if items:
                block_data.append({"kw": kw, "items": items})
            time.sleep(1.2)
        if block_data:  # 取れたときだけキャッシュを更新(取れない日は前回分を保持)
            cache = {"rising": rising, "blocks": block_data,
                     "ts": datetime.now(JST).strftime("%m/%d %H:%M")}
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        else:
            rising, block_data = cache.get("rising", []), cache.get("blocks", [])
    else:
        rising, block_data = cache.get("rising", []), cache.get("blocks", [])

    rising_blocks = []
    for b in block_data:
        rows = "\n".join(_item_row(it) for it in b["items"]) if b["items"] else \
            '<li class="row"><div class="meta"><p class="iname">(デモ表示)</p></div></li>'
        rising_blocks.append(
            f'<h3 class="kwhead">🔥 {escape(b["kw"])}</h3>\n<ol class="list">{rows}\n</ol>')
    cache_ts = f"・最終解析 {cache['ts']}" if cache.get("ts") else ""

    own_chips = "\n".join(
        f'<a class="chip" href="./?q={urllib.parse.quote(w)}">{escape(w)} <b>×{c}</b></a>'
        for w, c, _ in own) or '<p class="empty">データ蓄積中です(新着予約が貯まると表示されます)</p>'

    rising_html = "\n".join(rising_blocks) or \
        '<p class="empty">本日は世間トレンドを取得できませんでした(自動で再試行します)</p>'

    tabs = ('<a class="tab tablink" href="../">🏠 すべて</a>\n'
            '<a class="tab tablink active" href="./">🔥 急上昇</a>\n'
            '<a class="tab tablink" href="../calendar/">📅 発売カレンダー</a>\n'
            '<a class="tab tablink" href="../released/">✅ 発売済み</a>\n'
            + "\n".join(f'<a class="tab tablink" href="../{g["slug"]}/">{g["icon"]} {escape(g["name"])}</a>'
                        for g in categories))
    _ads = os.environ.get("ADSENSE_CLIENT", "").strip()
    adsense = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
               f'?client={escape(_ads, quote=True)}" crossorigin="anonymous"></script>') if _ads else ""
    canonical = (f'<link rel="canonical" href="{escape(site_url + "trend/", quote=True)}">'
                 if site_url else "")
    title = f"急上昇トレンド|{site_name}"
    desc = "ホビー界隈でいま話題のワードと、予約が集中している商品を毎日自動解析。"
    demo_note = ('<div class="demo-note">⚠ デモデータ表示中です。本番運用が始まると実データに切り替わります。</div>'
                 if demo else "")

    search_cfg = {
        "yahooAppId": os.environ.get("YAHOO_APP_ID", "").strip(),
        "amazonTag": os.environ.get("AMAZON_PARTNER_TAG", "").strip(),
        "dataUrl": "../data.json",
        "searchApiUrl": os.environ.get("SEARCH_API_URL", "").strip(),
    }
    search_js = ('<script id="cross-search-script">'
                 + SEARCH_JS.replace("__SEARCH_CONFIG__", json.dumps(search_cfg, ensure_ascii=False))
                 + "</script>")

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc, quote=True)}">
{canonical}
<meta property="og:title" content="{escape(title, quote=True)}">
<meta property="og:description" content="{escape(desc, quote=True)}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
{adsense}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Murecho:wght@700;900&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {{ --paper:#F5F6F8; --ink:#14181F; --rule:#E7E9EF; --accent:#0BA678;
  --accent-bg:#E3F5EE; --marker:#FFE066; --muted:#707888; --card:#fff; --new:#E5304F; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"Noto Sans JP",sans-serif; background:var(--paper); color:var(--ink);
  line-height:1.6; -webkit-font-smoothing:antialiased; }}
header {{ background:var(--card); color:var(--ink); padding:14px 16px 12px; border-bottom:1px solid var(--rule); }}
.head-inner {{ max-width:780px; margin:0 auto; }}
.logo {{ font-family:"Murecho","Noto Sans JP",sans-serif; font-size:21px; font-weight:900; }}
.logo a {{ color:var(--ink); text-decoration:none; }}
.logo .y {{ color:var(--accent); }}
.pagename {{ font-size:12px; font-weight:700; margin-top:3px; color:var(--muted); }}
.updated {{ display:inline-block; margin-top:6px; color:var(--accent);
  font-size:12px; font-weight:700; }}
.ad-label {{ font-size:11px; color:var(--muted); text-align:center; padding:5px 12px;
  border-bottom:1px solid var(--rule); }}
.demo-note {{ max-width:780px; margin:12px auto 0; padding:10px 14px; background:#FFF3CC;
  border:2px dashed #D9A400; border-radius:6px; font-size:13px; font-weight:700; }}
.tabs {{ position:sticky; top:0; z-index:20; background:color-mix(in srgb, var(--paper) 88%, transparent);
  backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); box-shadow:0 1px 0 var(--rule);
  display:flex; gap:8px; overflow-x:auto; padding:10px 16px 12px; scrollbar-width:thin; scrollbar-color:#AEB6C4 transparent;
  touch-action:pan-x; overscroll-behavior-x:contain; -webkit-overflow-scrolling:touch; }}
.tabs::-webkit-scrollbar {{ height:8px; }}
.tabs::-webkit-scrollbar-track {{ background:transparent; }}
.tabs::-webkit-scrollbar-thumb {{ background:#AEB6C4; border-radius:999px; border:2px solid transparent; background-clip:content-box; }}
.tabs::-webkit-scrollbar-thumb:hover {{ background:#7D8796; background-clip:content-box; }}
.tab {{ flex:0 0 auto; font-weight:700; font-size:13px; color:var(--ink); background:var(--card);
  border:1px solid var(--rule); border-radius:999px;
  padding:8px 14px; text-decoration:none; display:inline-block; white-space:nowrap; }}
.tab.active {{ background:var(--ink); border-color:var(--ink); color:#fff; }}
main {{ max-width:780px; margin:0 auto; padding:18px 14px 40px; }}
h2 {{ font-size:17px; font-weight:900; margin:18px 0 4px; padding-left:12px;
  border-left:6px solid var(--accent); }}
.lead {{ font-size:12px; color:var(--muted); margin-bottom:12px; }}
.chips {{ display:flex; flex-wrap:wrap; gap:8px; }}
.chip {{ background:var(--ink); color:#fff; text-decoration:none; font-weight:700;
  font-size:13px; padding:8px 14px; border-radius:999px; }}
.chip b {{ color:#7FE7C4; font-weight:900; margin-left:3px; }}
.kwhead {{ font-size:15px; font-weight:900; margin:16px 0 8px; }}
.list {{ list-style:none; background:var(--card); border:1px solid var(--rule);
  border-radius:16px; overflow:hidden; }}
.row {{ display:grid; grid-template-columns:72px 1fr auto; gap:12px; align-items:center;
  padding:12px; border-bottom:1px solid var(--rule); }}
.row:last-child {{ border-bottom:none; }}
.thumb img {{ width:72px; height:72px; object-fit:contain; border:1px solid var(--rule);
  border-radius:6px; background:#fff; }}
.noimg {{ width:72px; height:72px; display:grid; place-items:center; text-align:center;
  border:1px dashed var(--rule); border-radius:6px; color:var(--muted); font-size:10px; }}
.iname {{ font-size:12.5px; display:-webkit-box; -webkit-line-clamp:2;
  -webkit-box-orient:vertical; overflow:hidden; }}
.price {{ font-family:"Murecho",sans-serif; font-weight:900; font-size:17px; font-variant-numeric:tabular-nums; }}
.price small {{ font-size:11px; }}
.shop {{ font-size:11px; color:var(--muted); }}
.cta {{ background:var(--accent); color:#fff; font-weight:700; font-size:12px;
  text-decoration:none; padding:9px 16px; border-radius:999px; white-space:nowrap;
  border:none; }}
.empty {{ font-size:13px; color:var(--muted); padding:14px; background:#fff;
  border:1px dashed var(--rule); border-radius:8px; }}
.news {{ list-style:none; background:var(--card); border:1.5px solid var(--ink);
  border-radius:10px; overflow:hidden; }}
.nrow {{ padding:11px 14px; border-bottom:1px solid var(--rule); }}
.nrow:last-child {{ border-bottom:none; }}
.nrow a {{ color:var(--ink); font-size:13px; font-weight:500; text-decoration:none; }}
.nrow a:hover {{ text-decoration:underline; }}
.nsrc {{ display:block; font-size:11px; color:var(--muted); margin-top:2px; }}
footer {{ border-top:2px solid var(--ink); background:#fff; padding:22px 16px 32px;
  font-size:12px; color:var(--muted); }}
.foot-inner {{ max-width:780px; margin:0 auto; }}
@media (max-width:560px) {{ .row {{ grid-template-columns:60px 1fr; }}
  .thumb img,.noimg {{ width:60px; height:60px; }} .cta {{ grid-column:2; justify-self:start; }} }}
/* ===== PC幅: 関連商品をグリッド表示に ===== */
@media (min-width:860px) {{
  .head-inner, main, .foot-inner {{ max-width:1100px; }}
  .list {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));
    gap:14px; background:none; border:none; border-radius:0; }}
  .row {{ grid-template-columns:1fr; border:1px solid var(--rule); border-radius:14px;
    background:var(--card); border-bottom:1px solid var(--rule); align-items:stretch; }}
  .thumb img, .noimg {{ width:100%; height:150px; }}
  .cta {{ width:100%; text-align:center; margin-top:4px; }}
  .iname {{ -webkit-line-clamp:3; }}
}}
{SEARCH_CSS}
</style>
</head>
<body>
<header>
  <div class="head-inner">
    <h1 class="logo"><a href="../">予約開始<span class="y">レーダー</span></a></h1>
    <p class="pagename">🔥 急上昇トレンド(毎日自動解析)</p>
    <span class="updated">📅 {updated} 更新</span>
  </div>
</header>
<div class="ad-label">本ページはプロモーション(楽天・Yahoo!ショッピング等のアフィリエイト広告)を含みます</div>
{demo_note}
{SEARCH_HTML}
<nav class="tabs">
{tabs}
</nav>

<main>
  <h2>いま予約が集中しているワード</h2>
  <p class="lead">このサイトが直近7日間にキャッチした新着予約{len(feed_items)}件を頻度解析した結果です。タップで横断検索できます。</p>
  <div class="chips">
{own_chips}
  </div>

  <h2>ニュース・ネットで話題のワード</h2>
  <p class="lead">ホビー系ニュースサイトとはてなブックマークの直近48時間の見出し{news_count}本を解析した結果です。タップで横断検索できます。</p>
  <div class="chips">
{news_chips}
  </div>

  <h2>注目ヘッドライン</h2>
  <ul class="news">
{heads_html}
  </ul>

  <h2>世間の急上昇ワードと関連商品</h2>
  <p class="lead">Google検索で急上昇中のホビー関連ワードと、その関連商品です(1日3回解析{cache_ts})。</p>
{rising_html}
</main>

<footer>
  <div class="foot-inner">
    <p>トレンドは自動解析のため、文脈と無関係な語が混ざることがあります。価格・在庫はリンク先でご確認ください。</p>
    <p><a href="../">← トップ(全カテゴリの新着予約)へ戻る</a> ・ <a href="../privacy/">プライバシーポリシー</a></p>
  </div>
</footer>
{search_js}
</body>
</html>
"""
    page_dir = os.path.join(out_dir, "trend")
    os.makedirs(page_dir, exist_ok=True)
    with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"トレンドページ生成: 自前ワード{len(own)}件 / 世間ワード{len(rising)}件")


if __name__ == "__main__":
    # 単体デモ実行
    demo_cats = [{"slug": "pokemon-card", "icon": "🃏", "name": "ポケモンカード"}]
    build_trend_page(os.path.join(HERE, "docs"), demo_cats, "予約開始レーダー", "", True)
