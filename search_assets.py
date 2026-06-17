# -*- coding: utf-8 -*-
"""横断検索バー(楽天+Yahoo!)の部品。generate.pyから読み込まれます"""

SEARCH_CSS = """
/* ===== 横断検索 ===== */
.search { background: var(--card); border-bottom: 1px solid var(--rule); padding: 14px 14px 12px; }
.search-inner { max-width: 780px; margin: 0 auto; }
.sbar { display: flex; gap: 8px; }
.sbar input[type=search] { flex: 1; font: inherit; font-size: 15px; padding: 11px 14px;
  border: 1px solid var(--rule); border-radius: 999px; background: var(--paper); min-width: 0; }
.sbar input[type=search]:focus { outline: 3px solid var(--green); outline-offset: 1px; }
.sbar button { font: inherit; font-weight: 700; font-size: 14px; color: #fff;
  background: var(--green); border: none; border-radius: 999px;
  padding: 0 18px; cursor: pointer; white-space: nowrap; }
.sopts { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center;
  margin-top: 8px; font-size: 12px; color: var(--ink); }
.sopts label { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.sopts label:has(input:disabled) { opacity: .55; cursor: not-allowed; }
.sopts select { font: inherit; font-size: 12px; padding: 2px 4px; border: 1px solid var(--rule); border-radius: 5px; }
.sprice input { width: 76px; font: inherit; font-size: 12px; padding: 3px 6px;
  border: 1px solid var(--rule); border-radius: 5px; background: var(--card); color: var(--ink); }
.rates-toggle { background: none; border: none; color: var(--green); font-weight: 700;
  font-size: 12px; cursor: pointer; text-decoration: underline; padding: 0; }
.rates { display: none; margin-top: 8px; padding: 10px 12px; background: var(--green-bg);
  border-radius: 8px; font-size: 12px; align-items: center; gap: 8px 16px; flex-wrap: wrap; }
.rates.open { display: flex; }
.rates input { width: 56px; font: inherit; font-size: 13px; padding: 3px 6px;
  border: 1px solid var(--rule); border-radius: 5px; text-align: right; }
.sstatus { margin-top: 10px; font-size: 12.5px; color: var(--muted); }
.sactions { display: none; margin-top: 10px; }
.sactions.show { display: flex; gap: 8px; flex-wrap: wrap; }
.shome { font: inherit; font-size: 12px; font-weight: 700; color: var(--ink);
  background: var(--card); border: 1px solid var(--rule); border-radius: 999px;
  padding: 7px 12px; cursor: pointer; }
.sresults { list-style: none; margin-top: 10px; background: var(--card);
  border: 1px solid var(--rule); border-radius: 16px; overflow: hidden; }
.sresults:empty { display: none; }
.sr-row { display: grid; grid-template-columns: 64px 1fr auto; gap: 10px;
  padding: 11px 12px; border-bottom: 1px solid var(--rule); align-items: center; }
.sr-row:last-child { border-bottom: none; }
.sr-empty { padding: 16px; text-align: center; font-size: 12.5px; color: var(--muted); }
.sr-row img { width: 64px; height: 64px; object-fit: contain;
  border: 1px solid var(--rule); border-radius: 6px; background: #fff; }
.sr-name { font-size: 12.5px; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
.sr-sub { font-size: 12px; margin-top: 3px; }
.sr-price { font-weight: 700; font-size: 16px; font-variant-numeric: tabular-nums; }
.sr-eff { color: var(--green); font-size: 11.5px; font-weight: 700; margin-left: 6px; }
.unitchip { display: inline-block; background: var(--marker); font-weight: 700;
  font-size: 11px; padding: 1px 7px; border-radius: 3px; margin-left: 6px; }
.sr-shop { font-size: 11px; color: var(--muted); margin-top: 1px; }
.sr-cta { background: var(--ink); color: #fff; font-weight: 700; font-size: 12px;
  text-decoration: none; padding: 8px 14px; border-radius: 999px; white-space: nowrap; }
.mall { display: inline-block; font-size: 10.5px; font-weight: 700; padding: 1px 7px;
  border-radius: 3px; margin-right: 6px; vertical-align: 1px; }
.mall.rakuten { background: #FDEAEA; color: #BF0000; }
.mall.yahoo { background: #EDEAFB; color: #5B21B6; }
@media (max-width: 560px) { .sr-row { grid-template-columns: 56px 1fr; }
  .sr-cta { grid-column: 2; justify-self: start; } .sr-row img { width: 56px; height: 56px; } }
/* ===== 予測変換(サジェスト) ===== */
.swrap { position: relative; flex: 1; min-width: 0; display: flex; }
.swrap input[type=search] { width: 100%; }
.sugg { position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 30;
  list-style: none; background: var(--card); border: 1px solid var(--rule); border-radius: 14px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.18); overflow: hidden; }
.sugg:empty { display: none; }
.sugg li { padding: 10px 14px; font-size: 14px; cursor: pointer;
  border-bottom: 1px solid var(--rule); display: flex; align-items: center; gap: 8px; }
.sugg li:last-child { border-bottom: none; }
.sugg li.sel, .sugg li:hover { background: var(--green-bg); }
.sugg li .tagh { font-size: 10.5px; font-weight: 700; color: var(--muted);
  border: 1px solid var(--rule); border-radius: 3px; padding: 0 5px; flex-shrink: 0; }
.sugg li b { font-weight: 900; }
"""

SEARCH_HTML = """
<section class="search">
  <div class="search-inner">
    <form class="sbar" id="sform" autocomplete="off">
      <div class="swrap">
        <input type="search" id="sq" placeholder="商品名で検索(楽天は検知済み商品/Yahoo!は全件、例: ねんどろいど)" aria-label="商品検索" role="combobox" aria-expanded="false" aria-controls="sugg">
        <ul class="sugg" id="sugg" role="listbox"></ul>
      </div>
      <button type="submit">検索</button>
    </form>
    <div class="sopts">
      <label><input type="checkbox" id="opt-free" checked> 送料無料のみ</label>
      <label id="rakuten-label" title="楽天市場の全商品ではなく、このサイトが検知した商品の中から探します"><input type="checkbox" id="opt-rakuten" checked> <span id="rakuten-label-text">楽天(検知済み商品)</span></label>
      <label><input type="checkbox" id="opt-yahoo" checked> Yahoo!</label>
      <label>並び替え
        <select id="opt-sort">
          <option value="price">価格が安い順</option>
          <option value="unit">単価が安い順</option>
          <option value="eff">ポイント込み実質順</option>
        </select>
      </label>
      <label class="sprice">価格 <input type="number" id="opt-min" min="0" step="100" placeholder="下限"> - <input type="number" id="opt-max" min="0" step="100" placeholder="上限"></label>
      <button type="button" class="rates-toggle" id="rates-toggle">ポイント還元率を設定</button>
    </div>
    <div class="rates" id="rates">
      <span>あなたの還元率:</span>
      <label>楽天 <input type="number" id="rate-rakuten" min="0" max="30" step="0.5" value="1">%</label>
      <label>Yahoo!(PayPay) <input type="number" id="rate-yahoo" min="0" max="30" step="0.5" value="1">%</label>
      <span>→「実質順」はポイント分を引いた価格で並びます</span>
    </div>
    <p class="sstatus" id="sstatus"></p>
    <div class="sactions" id="sactions">
      <button type="button" class="shome" id="search-home">ホームに戻る</button>
    </div>
    <ol class="sresults" id="sresults"></ol>
  </div>
</section>
"""

SEARCH_JS = r"""
(function () {
  var CFG = __SEARCH_CONFIG__;
  function $(id) { return document.getElementById(id); }
  var state = { items: [] };
  // searchApiUrl(中継Worker)が設定されていれば、楽天もYahoo!もWorker経由で全件検索する。
  // 未設定の場合は、楽天はaccessKeyをブラウザに出せないためサイト内検知済み商品のみ、
  // Yahoo!はyahooAppIdがあればブラウザから直接検索する(従来どおりのフォールバック)。
  var useRemote = !!CFG.searchApiUrl;

  // ---- 見た目とAPI設定のズレを防ぐ: 未設定のモールはチェックボックスを無効化して明示する ----
  if (!useRemote && !CFG.yahooAppId) {
    var yCb = $("opt-yahoo");
    if (yCb) {
      yCb.checked = false;
      yCb.disabled = true;
      var yLabel = yCb.closest("label");
      if (yLabel) yLabel.title = "Yahoo!のアプリケーションIDが未設定のため、現在Yahoo!検索は利用できません";
    }
  }
  if (useRemote) {
    var rLabel = $("rakuten-label"), rText = $("rakuten-label-text"), sq0 = $("sq");
    if (rLabel) rLabel.removeAttribute("title");
    if (rText) rText.textContent = "楽天";
    if (sq0) sq0.placeholder = "商品名で楽天とYahoo!をまとめて検索(例: ねんどろいど)";
  }

  // ---- 単価の自動判定(サイト本体と同じ考え方のJS版) ----
  function norm(s) {
    s = s.normalize("NFKC").toLowerCase();
    s = s.replace(/×/g, "✕").replace(/リットル/g, "l").replace(/ℓ/g, "l").replace(/キロ/g, "kg");
    s = s.replace(/([0-9個袋本箱杯ル])\s*x\s*(?=[0-9])/g, "$1✕");
    return s;
  }
  function pairOrMax(t, unit, scale) {
    scale = scale || 1; var best = 0, m;
    var rePair = new RegExp("([0-9]+(?:\\.[0-9]+)?)\\s*" + unit + "\\s*✕\\s*([0-9]+)", "g");
    while ((m = rePair.exec(t))) best = Math.max(best, parseFloat(m[1]) * parseInt(m[2], 10) * scale);
    var reOne = new RegExp("([0-9]+(?:\\.[0-9]+)?)\\s*" + unit, "g");
    while ((m = reOne.exec(t))) best = Math.max(best, parseFloat(m[1]) * scale);
    return best || null;
  }
  function detectUnit(name) {
    var t = norm(name), q;
    q = Math.max(pairOrMax(t, "kg") || 0, pairOrMax(t, "g(?![a-z])", 0.001) || 0);
    if (q >= 0.3) return { unit: "kg", qty: q };
    var vol = 0, m = t.match(/([0-9]+(?:\.[0-9]+)?)\s*l(?![a-z])/);
    if (m) vol = parseFloat(m[1]);
    if (!vol) { m = t.match(/([0-9]+(?:\.[0-9]+)?)\s*ml/); if (m) vol = parseFloat(m[1]) / 1000; }
    if (vol) {
      m = t.match(/✕\s*([0-9]+)\s*本/) || t.match(/([0-9]+)\s*本/);
      var n = m ? parseInt(m[1], 10) : 1;
      if (n <= 100) return { unit: "L", qty: vol * n };
    }
    q = pairOrMax(t, "ロール");
    if (q) { m = t.match(/([0-9]+(?:\.[0-9]+)?)\s*倍/); if (m && +m[1] > 1 && +m[1] <= 8) q *= +m[1];
      return { unit: "ロール", qty: q }; }
    q = pairOrMax(t, "(?:箱|パック)"); if (q && q >= 3) return { unit: "箱", qty: q };
    q = pairOrMax(t, "(?:袋|杯分|杯|包)"); if (q && q >= 10) return { unit: "杯", qty: q };
    return null;
  }
  function fmt(v) { return v < 100 ? v.toFixed(1) : Math.round(v).toLocaleString(); }

  // ---- 還元率の保存(ブラウザに記憶) ----
  function loadRates() {
    try { var r = JSON.parse(localStorage.getItem("sokone_rates") || "{}");
      if (r.r != null) $("rate-rakuten").value = r.r;
      if (r.y != null) $("rate-yahoo").value = r.y; } catch (e) {}
  }
  function saveRates() {
    try { localStorage.setItem("sokone_rates",
      JSON.stringify({ r: +$("rate-rakuten").value, y: +$("rate-yahoo").value })); } catch (e) {}
  }

  // ---- 生成済みデータ検索。APIキーを公開HTMLに出さないため、ブラウザから楽天APIは直接叩かない。 ----
  var dataPromise = null;
  function loadSiteData() {
    if (!dataPromise) {
      dataPromise = fetch(CFG.dataUrl || "data.json", { cache: "no-store" })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) {
          var out = [];
          (d.genres || []).forEach(function (g) {
            (g.items || []).forEach(function (it) {
              out.push({ mall: "rakuten", name: it.name || "", price: +it.price || 0,
                url: it.url || "", image: it.image || "", shop: it.shop || g.name || "",
                free: false, cat: g.name || "", isNew: !!it.is_new, hot: !!it.hot });
            });
          });
          return out;
        });
    }
    return dataPromise;
  }
  function searchLocal(q) {
    var terms = sNorm(q).split(/\s+/).filter(Boolean);
    return loadSiteData().then(function (items) {
      return items.filter(function (it) {
        var hay = sNorm([it.name, it.shop, it.cat].join(" "));
        return terms.every(function (t) { return hay.indexOf(t) >= 0; });
      });
    });
  }
  function getJSON(url) {
    return fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }
  function searchRemote(q, freeOnly) {
    if (!CFG.searchApiUrl) return Promise.resolve([]);
    var p = new URLSearchParams({ q: q });
    if (freeOnly) p.set("free", "1");
    var url = CFG.searchApiUrl.replace(/\/+$/, "") + "?" + p;
    return getJSON(url).then(function (d) {
      return (d.items || []).map(function (it) {
        return { mall: it.mall === "yahoo" ? "yahoo" : "rakuten", name: it.name || "", price: +it.price || 0,
          url: it.url || "", image: it.image || "", shop: it.shop || "", free: !!it.free };
      });
    });
  }
  function searchYahoo(q, freeOnly) {
    if (!CFG.yahooAppId) return Promise.resolve([]);
    var p = new URLSearchParams({ appid: CFG.yahooAppId, query: q,
      results: "20", in_stock: "true", condition: "new" });
    var url = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch?" + p;
    return getJSON(url).then(function (d) {
      return (d.hits || []).filter(function (it) {
        var code = it.shipping && it.shipping.code;
        return freeOnly ? code === 2 : true;
      }).map(function (it) {
        return { mall: "yahoo", name: it.name || "", price: +it.price || 0,
          url: it.url || "", image: (it.image && it.image.medium) || "",
          shop: (it.seller && it.seller.name) || "",
          free: it.shipping && it.shipping.code === 2 };
      });
    });
  }

  // ---- 並び替えと描画 ----
  function effPrice(it) {
    var rate = it.mall === "rakuten" ? +$("rate-rakuten").value : +$("rate-yahoo").value;
    return it.price * (1 - Math.min(Math.max(rate || 0, 0), 30) / 100);
  }
  function sortItems(items) {
    var mode = $("opt-sort").value;
    var min = $("opt-min").value !== "" ? +$("opt-min").value : null;
    var max = $("opt-max").value !== "" ? +$("opt-max").value : null;
    var arr = items.filter(function (it) {
      return (min == null || it.price >= min) && (max == null || it.price <= max);
    });
    if (mode === "unit") {
      arr.sort(function (a, b) {
        if (!!a.u !== !!b.u) return a.u ? -1 : 1;
        if (a.u && b.u) {
          if (a.u.unit !== b.u.unit) return a.u.unit < b.u.unit ? -1 : 1;
          return a.price / a.u.qty - b.price / b.u.qty;
        }
        return a.price - b.price;
      });
    } else if (mode === "eff") {
      arr.sort(function (a, b) { return effPrice(a) - effPrice(b); });
    } else {
      arr.sort(function (a, b) { return a.price - b.price; });
    }
    return arr;
  }
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function render() {
    var items = sortItems(state.items).slice(0, 30);
    var ol = $("sresults"); ol.innerHTML = "";
    if (!items.length && state.query) {
      var rp = new URLSearchParams({ sitem: state.query });
      var ap = new URLSearchParams({ k: state.query });
      if (CFG.amazonTag) ap.set("tag", CFG.amazonTag);
      ol.innerHTML =
        '<li class="sr-empty">' + (useRemote ? "見つかりませんでした。" : "検知済み商品には見つかりませんでした。") +
        '<br><br><a class="sr-cta" href="https://search.rakuten.co.jp/search/mall?' + rp.toString() +
        '" target="_blank" rel="nofollow sponsored noopener">楽天市場で検索</a> ' +
        '<a class="sr-cta" href="https://www.amazon.co.jp/s?' + ap.toString() +
        '" target="_blank" rel="nofollow sponsored noopener">Amazonで検索</a></li>';
      return;
    }
    if (!items.length && state.items.length) {
      ol.innerHTML = '<li class="sr-empty">価格条件に合う商品がありません。</li>';
      return;
    }
    items.forEach(function (it) {
      var li = document.createElement("li"); li.className = "sr-row";
      var unitChip = it.u ? '<span class="unitchip">約' + fmt(it.price / it.u.qty) + "円/" + it.u.unit + "</span>" : "";
      var rate = it.mall === "rakuten" ? +$("rate-rakuten").value : +$("rate-yahoo").value;
      var eff = (rate > 0 && $("opt-sort").value === "eff") ?
        '<span class="sr-eff">実質' + Math.round(effPrice(it)).toLocaleString() + "円</span>" : "";
      var ship = it.free ? "送料無料" : "送料別の場合あり";
      li.innerHTML =
        (it.image ? '<img src="' + esc(it.image) + '" alt="" loading="lazy">' : "<div></div>") +
        '<div><p class="sr-name"><span class="mall ' + it.mall + '">' +
        (it.mall === "rakuten" ? "楽天" : "Yahoo!") + "</span>" + esc(it.name) + "</p>" +
        '<p class="sr-sub"><span class="sr-price">' + it.price.toLocaleString() + "円</span>" + eff + unitChip +
        ' <span style="color:var(--muted)">・' + ship + '</span></p>' +
        '<p class="sr-shop">' + esc(it.shop) + "</p></div>" +
        '<a class="sr-cta" href="' + esc(it.url) + '" target="_blank" rel="nofollow sponsored noopener">商品を見る</a>';
      ol.appendChild(li);
    });
  }

  function doSearch(ev) {
    if (ev) ev.preventDefault();
    var q = $("sq").value.trim();
    if (!q) return;
    state.query = q;
    saveHist(q); hideSugg();
    var freeOnly = $("opt-free").checked;
    var useR = $("opt-rakuten").checked, useY = $("opt-yahoo").checked;
    $("sstatus").textContent = "検索中…"; $("sresults").innerHTML = "";
    Promise.allSettled([
      useR ? searchLocal(q) : Promise.resolve([]),
      useRemote ? searchRemote(q, freeOnly) : (useY ? searchYahoo(q, freeOnly) : Promise.resolve([])),
    ]).then(function (rs) {
      var items = [], fails = [], seen = {};
      function addRows(rows) {
        (rows || []).forEach(function (it) {
          if (it.mall === "rakuten" && !useR) return;
          if (it.mall === "yahoo" && !useY) return;
          var key = (it.url || it.mall + ":" + it.name).split("?")[0];
          if (key && !seen[key]) { seen[key] = 1; items.push(it); }
        });
      }
      if (rs[0].status === "fulfilled") addRows(rs[0].value);
      else if (useR) fails.push("サイト内データ");
      if (rs[1].status === "fulfilled") addRows(rs[1].value);
      else if (useRemote) fails.push("検索API");
      else if (useY) fails.push("Yahoo!");
      items.forEach(function (it) { it.u = detectUnit(it.name); });
      state.items = items;
      var msg = esc(items.length + "件ヒット");
      if (fails.length) msg += esc("(" + fails.join("・") + "は取得できませんでした)");
      if (!items.length && !fails.length) {
        msg = useRemote ? esc("見つかりませんでした。外部検索も確認できます。")
                         : esc("検知済み商品には見つかりませんでした。外部検索も確認できます。");
      }
      var ap = new URLSearchParams({ k: q });
      if (CFG.amazonTag) ap.set("tag", CFG.amazonTag);
      var rp = new URLSearchParams({ sitem: q });
      msg += ' ・ <a href="https://search.rakuten.co.jp/search/mall?' + rp.toString() +
        '" target="_blank" rel="nofollow sponsored noopener" style="color:var(--green);font-weight:700">楽天市場で検索 →</a>';
      msg += ' ・ <a href="https://www.amazon.co.jp/s?' + ap.toString() +
        '" target="_blank" rel="nofollow sponsored noopener" style="color:var(--green);font-weight:700">Amazonでも検索 →</a>';
      $("sstatus").innerHTML = msg;
      $("sactions").classList.add("show");
      render();
    });
  }

  // ---- 予測変換(ホビー用語辞書 + 検索履歴) ----
  var DICT = ["ポケモンカード","ポケモンカード BOX","ポケモンカード ハイクラスパック","ワンピースカード","ワンピースカード BOX","遊戯王","遊戯王 BOX","デュエルマスターズ","ヴァイスシュヴァルツ","バトルスピリッツ","MTG","ドラゴンボールカード","ガンプラ","ガンプラ HG","ガンプラ MG","ガンプラ RG","ガンプラ PG","ガンプラ SD","METAL BUILD","ROBOT魂","S.H.Figuarts","S.H.MonsterArts","超合金","フィギュア","スケールフィギュア","プライズフィギュア","ねんどろいど","figma","ポップアップパレード","ルックアップ","一番くじ","ぬいぐるみ","アクリルスタンド","缶バッジ","ゲームソフト","Switch ソフト","Switch2 ソフト","PS5 ソフト","コントローラー","amiibo","鉄道模型","Nゲージ","HOゲージ","トミカ","プラレール","ミニカー","ホットウィール","チョロQ","レゴ","ベイブレード","シルバニアファミリー","リカちゃん","仮面ライダー","仮面ライダー ベルト","ウルトラマン","スーパー戦隊","プリキュア","ガンダム","エヴァンゲリオン","ポケモン","星のカービィ","スプラトゥーン","ゼルダの伝説","マリオ","どうぶつの森","モンスターハンター","ファイナルファンタジー","ドラゴンクエスト","ペルソナ","ワンピース","鬼滅の刃","呪術廻戦","SPY×FAMILY","チェンソーマン","推しの子","ブルーロック","ハイキュー","ヒロアカ","NARUTO","ドラゴンボール","スラムダンク","名探偵コナン","セーラームーン","ちいかわ","サンリオ","すみっコぐらし","ポチャッコ","シナモロール","初音ミク","ホロライブ","にじさんじ","ウマ娘","ブルーアーカイブ","原神","崩壊スターレイル","ゼンレスゾーンゼロ","Fate","アズールレーン","アイドルマスター","ラブライブ","バンドリ","東方Project","ヴァイオレット・エヴァーガーデン","ジブリ","ディズニー","スター・ウォーズ","マーベル","ゴジラ","トランスフォーマー","Blu-ray 特典","アニメ Blu-ray","サウンドトラック","予約 特典付き","限定版","コレクターズエディション"];
  function kataToHira(s) {
    return s.replace(/[\u30a1-\u30f6]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x60); });
  }
  function sNorm(s) { return kataToHira(s.normalize("NFKC").toLowerCase()); }
  function loadHist() {
    try { return JSON.parse(localStorage.getItem("yoyaku_hist") || "[]"); } catch (e) { return []; }
  }
  function saveHist(q) {
    try { var h = loadHist().filter(function (x) { return x !== q; });
      h.unshift(q); localStorage.setItem("yoyaku_hist", JSON.stringify(h.slice(0, 10))); } catch (e) {}
  }
  var selIdx = -1;
  function hideSugg() { $("sugg").innerHTML = ""; selIdx = -1; $("sq").setAttribute("aria-expanded", "false"); }
  function highlight(term, q) {
    var n = sNorm(term), i = n.indexOf(sNorm(q));
    if (i < 0 || !q) return esc(term);
    return esc(term.slice(0, i)) + "<b>" + esc(term.slice(i, i + q.length)) + "</b>" + esc(term.slice(i + q.length));
  }
  function showSugg() {
    var q = $("sq").value.trim();
    var nq = sNorm(q);
    var hist = loadHist();
    var out = [];
    if (!q) {
      hist.slice(0, 5).forEach(function (h) { out.push({ t: h, tag: "履歴" }); });
    } else {
      hist.forEach(function (h) { if (sNorm(h).indexOf(nq) === 0 && out.length < 3) out.push({ t: h, tag: "履歴" }); });
      var starts = [], includes = [];
      DICT.forEach(function (d) {
        var nd = sNorm(d);
        if (out.some(function (o) { return o.t === d; })) return;
        if (nd.indexOf(nq) === 0) starts.push(d);
        else if (nd.indexOf(nq) >= 0) includes.push(d);
      });
      starts.concat(includes).slice(0, 8 - out.length).forEach(function (d) { out.push({ t: d, tag: "" }); });
    }
    var ul = $("sugg"); ul.innerHTML = "";
    out.forEach(function (o, i) {
      var li = document.createElement("li");
      li.setAttribute("role", "option");
      li.innerHTML = (o.tag ? '<span class="tagh">' + o.tag + "</span>" : "") + highlight(o.t, q);
      li.addEventListener("mousedown", function (ev) { ev.preventDefault();
        $("sq").value = o.t; hideSugg(); doSearch(); });
      ul.appendChild(li);
    });
    $("sq").setAttribute("aria-expanded", out.length ? "true" : "false");
  }
  $("sq").addEventListener("input", showSugg);
  $("sq").addEventListener("focus", showSugg);
  $("sq").addEventListener("blur", function () { setTimeout(hideSugg, 150); });
  $("sq").addEventListener("keydown", function (ev) {
    var lis = $("sugg").children;
    if (!lis.length) return;
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      selIdx = ev.key === "ArrowDown" ? (selIdx + 1) % lis.length : (selIdx - 1 + lis.length) % lis.length;
      for (var i = 0; i < lis.length; i++) lis[i].classList.toggle("sel", i === selIdx);
    } else if (ev.key === "Enter" && selIdx >= 0) {
      ev.preventDefault();
      $("sq").value = lis[selIdx].textContent.replace(/^履歴/, "");
      hideSugg(); doSearch();
    } else if (ev.key === "Escape") { hideSugg(); }
  });

  $("sform").addEventListener("submit", doSearch);
  $("search-home").addEventListener("click", function () {
    state.items = [];
    $("sq").value = "";
    $("sstatus").textContent = "";
    $("sresults").innerHTML = "";
    $("sactions").classList.remove("show");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  $("opt-sort").addEventListener("change", render);
  $("opt-min").addEventListener("input", render);
  $("opt-max").addEventListener("input", render);
  $("rates-toggle").addEventListener("click", function () { $("rates").classList.toggle("open"); });
  ["rate-rakuten", "rate-yahoo"].forEach(function (id) {
    $(id).addEventListener("change", function () { saveRates(); render(); });
  });
  loadRates();
  // トレンドページ等から「?q=ワード」付きで来たら自動で検索する
  try {
    var qp = new URLSearchParams(location.search).get("q");
    if (qp) { $("sq").value = qp; doSearch(); }
  } catch (e) {}
})();
"""
