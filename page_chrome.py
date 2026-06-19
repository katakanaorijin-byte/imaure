# -*- coding: utf-8 -*-
"""
ヘッダー(アプリバー)の共通部品。

generate.py / calendar_page.py / trends.py / released_page.py がそれぞれ
独自の<header>を持っていたため、ロゴの色・配置・余白がページごとに
バラバラになってしまっていた。ここに一本化し、全ページで同じ見た目になるようにする。
"""

import os
from html import escape

HEADER_CSS = """
/* ===== アプリバー(全ページ共通) ===== */
.appbar { background: var(--card); border-bottom: 1px solid var(--rule); padding: 14px 16px 12px; }
.appbar-in { max-width: 680px; margin: 0 auto; }
.brandrow { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.brand { font-size: 21px; font-weight: 900; letter-spacing: 0.01em;
  font-family: "Murecho", "Noto Sans JP", sans-serif; }
.brand a { color: inherit; text-decoration: none; }
.live { display: inline-flex; align-items: center; gap: 6px; flex: 0 0 auto;
  font-size: 12px; font-weight: 700; color: var(--green); white-space: nowrap;
  font-variant-numeric: tabular-nums; }
.pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--green); position: relative; }
.pulse::after { content: ""; position: absolute; inset: -4px; border-radius: 50%;
  border: 2px solid var(--green); opacity: 0; animation: ping 2.4s ease-out infinite; }
@keyframes ping { 0% { transform: scale(0.4); opacity: 0.7; } 70%, 100% { transform: scale(1); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .pulse::after { animation: none; } }
.tag { max-width: 680px; margin: 3px auto 0; font-size: 12px; color: var(--muted); }
.follow-strip { max-width: 680px; margin: 10px auto 0; padding: 10px 12px;
  background: color-mix(in srgb, var(--green-bg) 72%, var(--card));
  border: 1px solid color-mix(in srgb, var(--green) 28%, var(--rule));
  border-radius: 10px; display: flex; align-items: center; justify-content: space-between;
  gap: 10px; }
.follow-copy { min-width: 0; }
.follow-kicker { display: block; font-size: 11px; font-weight: 900; color: var(--green);
  letter-spacing: 0.02em; }
.follow-text { display: block; margin-top: 1px; font-size: 12.5px; font-weight: 700;
  color: var(--ink); line-height: 1.45; }
.follow-actions { display: flex; gap: 7px; flex: 0 0 auto; flex-wrap: wrap; justify-content: flex-end; }
.follow-action { font: inherit; font-size: 12px; font-weight: 900; line-height: 1;
  color: var(--ink); background: var(--card); border: 1px solid var(--rule);
  border-radius: 999px; padding: 8px 10px; text-decoration: none; cursor: pointer;
  white-space: nowrap; }
.follow-action.primary { background: var(--ink); border-color: var(--ink); color: #fff; }
.follow-action.share { border-color: color-mix(in srgb, var(--green) 32%, var(--rule)); }
.follow-action:focus-visible { outline: 3px solid var(--green); outline-offset: 2px; }
.ad-label { font-size: 10.5px; color: var(--muted); text-align: center; padding: 6px 12px 0; }
.demo-note { max-width: 680px; margin: 12px auto 0; padding: 10px 14px;
  background: #FFF6DB; border: 1px solid #E8C84A; border-radius: 12px;
  font-size: 12.5px; font-weight: 700; }
@media (min-width: 860px) {
  .appbar-in, .tag, .follow-strip, .demo-note { max-width: 1100px; }
}
@media (max-width: 520px) {
  .follow-strip { align-items: flex-start; flex-direction: column; }
  .follow-actions { width: 100%; justify-content: flex-start; }
}
@media (prefers-color-scheme: dark) {
  .demo-note { background: #332B0E; border-color: #8A7A1E; color: #F2E7AE; }
  .follow-action.primary { background: var(--green); border-color: var(--green); color: #08110D; }
}
"""


def render_header(home_href: str, updated: str, tagline: str) -> str:
    """appbar(ロゴ+更新時刻+説明文)のHTMLを作る。tagline は呼び出し側でエスケープ済みのHTML文字列を渡すこと"""
    x_account_url = os.environ.get("X_ACCOUNT_URL", "").strip()
    feed_href = home_href.rstrip("/") + "/feed.xml" if home_href not in ("", "./") else "./feed.xml"
    x_link = (f'\n      <a class="follow-action primary" href="{escape(x_account_url, quote=True)}" '
              'target="_blank" rel="noopener">Xで受け取る</a>') if x_account_url else ""
    share_js = ("var u=location.href.split('#')[0];"
                "var t=document.title.replace('|予約開始レーダー','');"
                "window.open('https://twitter.com/intent/tweet?text='+encodeURIComponent(t+'\\n'+u),'_blank','noopener');")
    return f"""<header class="appbar">
  <div class="appbar-in">
    <div class="brandrow">
      <h1 class="brand"><a href="{escape(home_href, quote=True)}">予約開始レーダー</a></h1>
      <span class="live"><i class="pulse"></i>{escape(updated)} 更新</span>
    </div>
  </div>
  <p class="tag">{tagline}</p>
  <div class="follow-strip">
    <p class="follow-copy">
      <span class="follow-kicker">見逃し防止に</span>
      <span class="follow-text">人気商品の予約開始・再販・抽選情報を自動チェック。あとで見返す人はブックマークへ。</span>
    </p>
    <div class="follow-actions">
      <button class="follow-action" type="button" onclick="alert('ブラウザのブックマークに追加して、あとで新着予約をチェックできます。');">ブックマーク</button>
      <button class="follow-action share" type="button" onclick="{escape(share_js, quote=True)}">このページをシェア</button>
{x_link}
      <a class="follow-action" href="{escape(feed_href, quote=True)}">RSS</a>
    </div>
  </div>
</header>
<p class="ad-label">本ページはプロモーション(楽天・Yahoo!ショッピング等のアフィリエイト広告)を含みます</p>"""
