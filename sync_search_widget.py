# -*- coding: utf-8 -*-
"""
横断検索バー(CSS/HTML/JS)を search_assets.py の最新内容で
docs/ 配下の生成済みHTMLに反映し直すツール。

generate.py をフルで動かすと商品データも再取得されるため、
楽天/Yahoo!のAPIキーが無い環境(ローカル等)で実行すると
本番の商品データがデモデータに置き換わってしまいます。

このスクリプトは商品カードや価格などのデータには触れず、
検索バー部分(CSS/HTML/JS)だけを今のテンプレートで上書きします。
APIキーは不要です(各ページに既に埋め込まれている設定値を維持します。
環境変数 YAHOO_APP_ID / AMAZON_PARTNER_TAG / SEARCH_API_URL を指定すればその値で上書きできます)。

使い方:
  python sync_search_widget.py
"""

import glob
import json
import os
import re

from search_assets import SEARCH_CSS, SEARCH_HTML, SEARCH_JS

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")

CSS_START = "/* ===== 横断検索 ===== */"
CFG_PATTERN = re.compile(r"var CFG = (\{.*?\});", re.DOTALL)
CSS_PATTERN = re.compile(re.escape(CSS_START) + r".*?(?=\n</style>)", re.DOTALL)
SECTION_PATTERN = re.compile(r'<section class="search">.*?</section>', re.DOTALL)
SCRIPT_PATTERN = re.compile(
    r'<script[^>]*>\s*\(function \(\) \{\s*var CFG = .*?</script>', re.DOTALL)

ENV_OVERRIDES = {
    "yahooAppId": "YAHOO_APP_ID",
    "amazonTag": "AMAZON_PARTNER_TAG",
    "searchApiUrl": "SEARCH_API_URL",
}
# ブラウザから楽天APIを直接叩く実装は廃止済み(accessKeyが必須でブラウザに置けないため)。
# 過去にこのスクリプトが埋め込んだ古いキーが残っていれば削除する。
OBSOLETE_KEYS = ("rakutenAppId", "rakutenAffiliateId")


def build_cfg(existing_html, prefix):
    """既存ページに埋め込まれた設定値を引き継ぎつつ、環境変数があれば上書きする"""
    cfg = {}
    m = CFG_PATTERN.search(existing_html)
    if m:
        try:
            cfg = json.loads(m.group(1))
        except Exception:
            cfg = {}
    for key in OBSOLETE_KEYS:
        cfg.pop(key, None)
    for key, env_name in ENV_OVERRIDES.items():
        val = os.environ.get(env_name)
        if val:
            cfg[key] = val.strip()
        else:
            cfg.setdefault(key, "")
    cfg["dataUrl"] = f"{prefix}data.json"
    return cfg


def sync_file(path, prefix):
    with open(path, encoding="utf-8-sig") as f:
        html = f.read()

    if '<section class="search">' not in html:
        return False  # 検索バーが無いページ(calendar/trend/privacy等)は対象外

    cfg = build_cfg(html, prefix)

    new_html = CSS_PATTERN.sub(lambda _m: SEARCH_CSS.strip("\n"), html, count=1)
    new_html = SECTION_PATTERN.sub(lambda _m: SEARCH_HTML.strip("\n"), new_html, count=1)

    js_block = ('<script id="cross-search-script">'
                + SEARCH_JS.replace("__SEARCH_CONFIG__", json.dumps(cfg, ensure_ascii=False))
                + "</script>")
    new_html = SCRIPT_PATTERN.sub(lambda _m: js_block, new_html, count=1)

    if new_html == html:
        return False

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_html)
    return True


def main():
    changed = []

    root = os.path.join(DOCS, "index.html")
    if os.path.exists(root) and sync_file(root, ""):
        changed.append(root)

    for sub in sorted(glob.glob(os.path.join(DOCS, "*", "index.html"))):
        if sync_file(sub, "../"):
            changed.append(sub)

    if changed:
        print(f"更新: {len(changed)}件")
        for c in changed:
            print(" -", os.path.relpath(c, HERE))
    else:
        print("変更なし(すべて最新の検索バーでした)")


if __name__ == "__main__":
    main()
