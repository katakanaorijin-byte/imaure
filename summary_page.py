# -*- coding: utf-8 -*-
"""
週次/月次まとめページ生成(予約開始レーダー用)。

Xで貼りやすく、検索にも拾われやすい「予約 一覧 最新」系の入口を作る。
"""

import json
import os
from datetime import datetime, timezone, timedelta
from html import escape

from page_chrome import HEADER_CSS, render_header
from search_assets import SEARCH_CSS, SEARCH_HTML, SEARCH_JS

JST = timezone(timedelta(hours=9))
SUMMARY_FIXED_TAGS = ["#予約開始", "#ホビー予約", "#ポケカ", "#ガンプラ"]
SHORT_CATEGORY_NAMES = {
    "ポケモンカード": "ポケカ",
    "ワンピースカード": "ワンピカード",
    "ガンプラ・プラモデル": "ガンプラ",
    "アニメBlu-ray・CD": "アニメBD/CD",
    "遊戯王・他カード": "遊戯王",
    "ねんどろいど・figma": "ねんどろいど",
}


def _row(it, g):
    img = (f'<img src="{escape(it.get("image", ""), quote=True)}" alt="" loading="lazy">'
           if it.get("image") else '<div class="noimg">画像<br>なし</div>')
    rel = f'<span class="when">{escape(it["release"])}発売</span>' if it.get("release") else ""
    hot = '<span class="mark">注目</span>' if it.get("hot") else ""
    return f"""
      <li class="row">
        <div class="thumb">{img}</div>
        <div class="meta">
          <p class="iname"><span class="cicon">{g["icon"]}</span>{escape(it["name"])}</p>
          <p class="sub"><span class="price">{int(it.get('price') or 0):,}<small>円</small></span> {rel} {hot}</p>
          <p class="shop">{escape(it.get("shop", ""))}</p>
        </div>
        <a class="cta" href="{escape(it['url'], quote=True)}" target="_blank" rel="nofollow sponsored noopener">予約ページへ</a>
      </li>"""


def _build_page(out_dir, data, site_name, site_url, demo, period):
    now = datetime.now(JST)
    updated = f"{now.hour:02d}:{now.minute:02d}"
    is_weekly = period == "weekly"
    slug = "weekly" if is_weekly else "monthly"
    label = "今週" if is_weekly else "今月"
    title = f"{label}の予約開始まとめ・ホビー予約一覧 最新|{site_name}"
    desc = (f"ポケカ・フィギュア・ガンプラ・ゲームなど、{label}チェックしたい予約開始・再販・抽選情報をカテゴリ別に一覧化。"
            "最新の受付中予約をまとめて確認できます。")

    sections = []
    total = 0
    max_per_cat = 5 if is_weekly else 8
    for g in data:
        items = list(g.get("items") or [])[:max_per_cat]
        if not items:
            continue
        total += len(items)
        rows = "\n".join(_row(it, g) for it in items)
        sections.append(
            f'<section class="block"><h2>{g["icon"]} {escape(g["name"])}の予約一覧 最新'
            f'<span class="count">{len(items)}件</span></h2>\n'
            f'<ol class="list">{rows}\n</ol>'
            f'<p class="more"><a href="../{g["slug"]}/">{escape(g["name"])}の予約をもっと見る</a></p></section>')
    sections_html = "\n".join(sections) or '<p class="empty">まとめ対象の商品がまだありません。</p>'

    tabs = ('<a class="tab tablink" href="../">🏠 すべて</a>\n'
            f'<a class="tab tablink{" active" if is_weekly else ""}" href="../weekly/">🗓 今週まとめ</a>\n'
            f'<a class="tab tablink{" active" if not is_weekly else ""}" href="../monthly/">📌 今月まとめ</a>\n'
            '<a class="tab tablink" href="../trend/">🔥 急上昇</a>\n'
            '<a class="tab tablink" href="../calendar/">📅 発売カレンダー</a>\n'
            '<a class="tab tablink" href="../released/">✅ 発売済み</a>\n'
            + "\n".join(f'<a class="tab tablink" href="../{g["slug"]}/">{g["icon"]} {escape(g["name"])}</a>'
                        for g in data))

    canonical = f'<link rel="canonical" href="{escape(site_url + slug + "/", quote=True)}">' if site_url else ""
    demo_note = '<div class="demo-note">⚠ デモデータ表示中です。</div>' if demo else ""
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Murecho:wght@700;900&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {{ --paper:#F5F6F8; --ink:#14181F; --rule:#E7E9EF; --accent:#0BA678;
  --accent-bg:#E3F5EE; --green:#0BA678; --green-bg:#E3F5EE;
  --marker:#FFE066; --muted:#707888; --card:#fff; --new:#E5304F; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"Noto Sans JP",sans-serif; background:var(--paper); color:var(--ink);
  line-height:1.6; -webkit-font-smoothing:antialiased; }}
{HEADER_CSS}
.tabs {{ position:sticky; top:0; z-index:20; background:color-mix(in srgb, var(--paper) 88%, transparent);
  backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); box-shadow:0 1px 0 var(--rule);
  display:flex; gap:8px; overflow-x:auto; padding:10px 16px 12px; scrollbar-width:thin; scrollbar-color:#AEB6C4 transparent;
  touch-action:pan-x; overscroll-behavior-x:contain; -webkit-overflow-scrolling:touch; }}
.tab {{ flex:0 0 auto; font-weight:700; font-size:13px; color:var(--ink); background:var(--card);
  border:1px solid var(--rule); border-radius:999px; padding:8px 14px; text-decoration:none; white-space:nowrap; }}
.tab.active {{ background:var(--ink); border-color:var(--ink); color:#fff; }}
main {{ max-width:780px; margin:0 auto; padding:18px 14px 40px; }}
.lead {{ font-size:13px; color:var(--muted); margin-bottom:14px; }}
.block {{ margin-top:18px; }}
h2 {{ font-size:17px; font-weight:900; margin:0 0 8px; padding-left:12px; border-left:6px solid var(--accent); }}
.count {{ font-size:12px; font-weight:700; color:var(--muted); margin-left:8px; }}
.list {{ list-style:none; background:var(--card); border:1px solid var(--rule); border-radius:16px; overflow:hidden; }}
.row {{ display:grid; grid-template-columns:64px 1fr auto; gap:12px; align-items:center; padding:12px; border-bottom:1px solid var(--rule); }}
.row:last-child {{ border-bottom:none; }}
.thumb img, .noimg {{ width:64px; height:64px; object-fit:contain; border:1px solid var(--rule); border-radius:6px; background:#fff; }}
.noimg {{ display:grid; place-items:center; text-align:center; color:var(--muted); font-size:10px; border-style:dashed; }}
.iname {{ font-size:12.5px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
.price {{ font-family:"Murecho",sans-serif; font-weight:900; font-size:16px; font-variant-numeric:tabular-nums; }}
.price small {{ font-size:11px; }}
.when, .mark {{ font-size:11.5px; font-weight:700; color:var(--accent); margin-left:8px; }}
.mark {{ color:var(--new); }}
.shop, .more {{ font-size:11.5px; color:var(--muted); }}
.more {{ margin:8px 2px 0; }}
.more a {{ color:var(--accent); font-weight:700; }}
.cta {{ background:var(--accent); color:#fff; font-weight:700; font-size:12px; text-decoration:none;
  padding:9px 16px; border-radius:999px; white-space:nowrap; }}
.empty {{ font-size:13px; color:var(--muted); padding:14px; background:#fff; border:1px dashed var(--rule); border-radius:8px; }}
footer {{ border-top:2px solid var(--ink); background:#fff; padding:22px 16px 32px; font-size:12px; color:var(--muted); }}
.foot-inner {{ max-width:780px; margin:0 auto; }}
@media (max-width:560px) {{ .row {{ grid-template-columns:56px 1fr; }} .thumb img,.noimg {{ width:56px; height:56px; }} .cta {{ grid-column:2; justify-self:start; }} }}
@media (min-width:860px) {{ main, .foot-inner {{ max-width:1100px; }} .list {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:14px; background:none; border:none; border-radius:0; }} .row {{ grid-template-columns:1fr; border:1px solid var(--rule); border-radius:14px; background:var(--card); align-items:stretch; }} .thumb img,.noimg {{ width:100%; height:150px; }} .cta {{ width:100%; text-align:center; }} .iname {{ -webkit-line-clamp:3; }} }}
@media (prefers-color-scheme: dark) {{ :root {{ --paper:#0E1117; --ink:#ECEEF3; --rule:#272C38; --accent:#2EC592; --accent-bg:#15302A; --green:#2EC592; --green-bg:#15302A; --marker:#5C4D12; --muted:#98A0B0; --card:#171B24; --new:#FF5D77; }} .tab.active {{ background:var(--accent); border-color:var(--accent); color:#08110D; }} footer {{ background:var(--card); }} .thumb img,.noimg,.empty {{ background:var(--card); }} .cta {{ color:#0E1117; }} }}
{SEARCH_CSS}
</style>
</head>
<body>
{render_header("../", updated, f"{label}の予約開始まとめ・ホビー予約一覧 最新")}
{demo_note}
{SEARCH_HTML}
<nav class="tabs">
{tabs}
</nav>
<main>
  <p class="lead">{label}見たい予約開始・再販・抽選情報をカテゴリ別に整理しました。Xで共有しやすいまとめ入口です。掲載中の商品は価格・受付状況が変わりやすいため、リンク先で最新情報をご確認ください。</p>
{sections_html}
</main>
<footer>
  <div class="foot-inner">
    <p><a href="../">← トップ(全カテゴリの新着予約)へ戻る</a> ・ <a href="../privacy/">プライバシーポリシー</a></p>
  </div>
</footer>
{search_js}
</body>
</html>
"""
    page_dir = os.path.join(out_dir, slug)
    os.makedirs(page_dir, exist_ok=True)
    with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{label}まとめページ生成: {total}件")


def build_summary_pages(out_dir, data, site_name, site_url, demo):
    _build_page(out_dir, data, site_name, site_url, demo, "weekly")
    _build_page(out_dir, data, site_name, site_url, demo, "monthly")
    write_social_templates(out_dir, data, site_url)


def _social_site_url(site_url: str) -> str:
    return (site_url or "https://katakanaorijin-byte.github.io/imaure/").rstrip("/") + "/"


def _social_categories(data, limit=4):
    cats = []
    for g in data:
        if g.get("items"):
            name = g.get("name", "")
            cats.append((g.get("icon", "・"), SHORT_CATEGORY_NAMES.get(name, name), g.get("tag", "")))
        if len(cats) >= limit:
            break
    return cats


def _summary_text(data, site_url, period):
    now = datetime.now(JST)
    label = "今週" if period == "weekly" else "今月"
    url = _social_site_url(site_url) + ("weekly/" if period == "weekly" else "monthly/")
    cat_text = " / ".join(name for _, name, _ in _social_categories(data))
    lines = [
        f"{label}のホビー予約開始まとめを更新しました。",
        "",
        f"{cat_text}など、",
        "予約開始・再販・抽選情報をカテゴリ別に整理しています。",
        "",
        url,
        " ".join(SUMMARY_FIXED_TAGS),
    ]
    return "\n".join(lines)


def _profile_text(site_url):
    return "\n".join([
        "予約開始レーダーでは、ホビーの予約開始・再販・抽選情報を自動チェックしています。",
        "",
        "ポケカ / ガンプラ / フィギュア / ゲームなど、受付中の予約一覧をまとめて確認できます。",
        _social_site_url(site_url),
        "#予約開始 #ホビー予約",
    ])


def write_social_templates(out_dir, data, site_url):
    texts = {
        "x-weekly-post.txt": _summary_text(data, site_url, "weekly"),
        "x-monthly-post.txt": _summary_text(data, site_url, "monthly"),
        "x-profile-post.txt": _profile_text(site_url),
    }
    for name, text in texts.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(text + "\n")
