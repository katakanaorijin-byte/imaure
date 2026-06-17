# -*- coding: utf-8 -*-
"""
発売済み・販売中まとめページ自動生成(予約開始レーダー用)

商品名は「予約」のままでも、商品名から読み取った発売時期が過ぎている商品を
カテゴリ別にまとめ、docs/released/index.html を作ります。
予約中の商品一覧(各カテゴリページ・新着フィード)からはこれらを取り除き、
「今すぐ買える」商品をここに集約します。generate.py から呼ばれます。
"""

import os
from datetime import datetime, timezone, timedelta
from html import escape

JST = timezone(timedelta(hours=9))


def _row(it, g):
    img = (f'<img src="{escape(it["image"], quote=True)}" alt="" loading="lazy">'
           if it.get("image") else '<div class="noimg">画像<br>なし</div>')
    rel = f'<span class="when">{escape(it["release"])}発売</span>' if it.get("release") else ""
    return f"""
      <li class="row">
        <div class="thumb">{img}</div>
        <div class="meta">
          <p class="iname"><span class="cicon">{g["icon"]}</span>{escape(it["name"])}</p>
          <p class="sub"><span class="price">{it['price']:,}<small>円</small></span> {rel}</p>
          <p class="shop">{escape(it.get("shop", ""))}</p>
        </div>
        <a class="cta" href="{escape(it['url'], quote=True)}" target="_blank" rel="nofollow sponsored noopener">商品ページへ</a>
      </li>"""


def build_released_page(out_dir, data, site_name, site_url, demo):
    now = datetime.now(JST)
    updated = f"{now.year}年{now.month}月{now.day}日 {now.hour:02d}:{now.minute:02d}"

    sections = []
    total = 0
    for g in data:
        items = g.get("released_items") or []
        if not items:
            continue
        total += len(items)
        rows = "\n".join(_row(it, g) for it in items)
        sections.append(
            f'<h2>{g["icon"]} {escape(g["name"])}<span class="count">{len(items)}件</span></h2>\n'
            f'<ol class="list">{rows}\n</ol>')
    sections_html = "\n".join(sections) or \
        '<p class="empty">発売済み・販売中と判定された商品はまだありません(運用が進むと貯まります)</p>'

    tabs = ('<a class="tab tablink" href="../">🏠 すべて</a>\n'
            '<a class="tab tablink" href="../trend/">🔥 急上昇</a>\n'
            '<a class="tab tablink" href="../calendar/">📅 発売カレンダー</a>\n'
            '<a class="tab tablink active" href="./">✅ 発売済み</a>\n'
            + "\n".join(f'<a class="tab tablink" href="../{g["slug"]}/">{g["icon"]} {escape(g["name"])}</a>'
                        for g in data))
    _ads = os.environ.get("ADSENSE_CLIENT", "").strip()
    adsense = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
               f'?client={escape(_ads, quote=True)}" crossorigin="anonymous"></script>') if _ads else ""
    canonical = (f'<link rel="canonical" href="{escape(site_url + "released/", quote=True)}">'
                 if site_url else "")
    title = f"発売済み・販売中まとめ|{site_name}"
    desc = "予約受付中だった商品のうち、発売時期を過ぎて発売済み・通常販売になったと思われる商品をまとめています。"
    demo_note = ('<div class="demo-note">⚠ デモデータ表示中です。</div>' if demo else "")

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
.lead {{ font-size:12px; color:var(--muted); margin-bottom:8px; }}
h2 {{ font-size:17px; font-weight:900; margin:20px 0 8px; padding-left:12px;
  border-left:6px solid var(--accent); }}
h2 .count {{ font-size:12px; font-weight:700; color:var(--muted); margin-left:8px; }}
.list {{ list-style:none; background:var(--card); border:1px solid var(--rule);
  border-radius:16px; overflow:hidden; }}
.row {{ display:grid; grid-template-columns:64px 1fr auto; gap:12px; align-items:center;
  padding:12px; border-bottom:1px solid var(--rule); }}
.row:last-child {{ border-bottom:none; }}
.thumb img {{ width:64px; height:64px; object-fit:contain; border:1px solid var(--rule);
  border-radius:6px; background:#fff; }}
.noimg {{ width:64px; height:64px; display:grid; place-items:center; text-align:center;
  border:1px dashed var(--rule); border-radius:6px; color:var(--muted); font-size:10px; }}
.cicon {{ margin-right:4px; }}
.iname {{ font-size:12.5px; display:-webkit-box; -webkit-line-clamp:2;
  -webkit-box-orient:vertical; overflow:hidden; }}
.price {{ font-family:"Murecho",sans-serif; font-weight:900; font-size:16px; font-variant-numeric:tabular-nums; }}
.price small {{ font-size:11px; }}
.when {{ font-size:11.5px; font-weight:700; color:var(--accent); margin-left:8px; }}
.shop {{ font-size:11px; color:var(--muted); }}
.cta {{ background:var(--accent); color:#fff; font-weight:700; font-size:12px;
  text-decoration:none; padding:9px 16px; border-radius:999px; white-space:nowrap;
  border:none; }}
.empty {{ font-size:13px; color:var(--muted); padding:14px; background:#fff;
  border:1px dashed var(--rule); border-radius:8px; }}
footer {{ border-top:2px solid var(--ink); background:#fff; padding:22px 16px 32px;
  font-size:12px; color:var(--muted); }}
.foot-inner {{ max-width:780px; margin:0 auto; }}
@media (max-width:560px) {{ .row {{ grid-template-columns:56px 1fr; }}
  .thumb img,.noimg {{ width:56px; height:56px; }} .cta {{ grid-column:2; justify-self:start; }} }}
@media (prefers-color-scheme: dark) {{
  :root {{ --paper:#F5F6F8; --ink:#14181F; --rule:#E7E9EF; --accent:#0BA678;
  --accent-bg:#E3F5EE; --marker:#FFE066; --muted:#707888; --card:#fff; --new:#E5304F; }}
  header {{ background:var(--card); }} .tab.active {{ background:var(--accent); border-color:var(--accent); color:#08110D; }}
  footer {{ background:var(--card); }}
  .empty, .thumb img, .noimg {{ background:var(--card); }}
  .demo-note {{ background:#3A3210; border-color:#9A8410; color:#F4E9B0; }}
  .cta {{ color:#0E1117; }}
}}
</style>
</head>
<body>
<header>
  <div class="head-inner">
    <h1 class="logo"><a href="../">予約開始<span class="y">レーダー</span></a></h1>
    <p class="pagename">✅ 発売済み・販売中まとめ(予約期間が終わった商品)</p>
    <span class="updated">📅 {updated} 更新</span>
  </div>
</header>
<div class="ad-label">本ページはプロモーション(楽天・Yahoo!ショッピング等のアフィリエイト広告)を含みます</div>
{demo_note}

<nav class="tabs">
{tabs}
</nav>

<main>
  <p class="lead">発売時期を過ぎ、発売済み・通常販売になったと思われる商品({total}件)をまとめました。商品名に「予約」が残っていても、出品者がタイトルを更新していないだけのことがあります。判定は商品名からの自動推定のため、必ずリンク先で在庫・価格をご確認ください。</p>
{sections_html}
</main>

<footer>
  <div class="foot-inner">
    <p><a href="../">← トップ(全カテゴリの新着予約)へ戻る</a> ・ <a href="../privacy/">プライバシーポリシー</a></p>
  </div>
</footer>
</body>
</html>
"""
    page_dir = os.path.join(out_dir, "released")
    os.makedirs(page_dir, exist_ok=True)
    with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"発売済みページ生成: {total}件")
