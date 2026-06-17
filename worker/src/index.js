/**
 * 横断検索バー用の中継API(Cloudflare Workers)。
 *
 * 楽天市場の検索APIは applicationId と accessKey をセットで要求し、
 * accessKey は秘密情報のためブラウザ(GitHub Pages)には置けない。
 * このWorkerはサーバー側でだけ accessKey を保持し、ブラウザからの
 * 検索リクエストを受けて楽天・Yahoo!のAPIを呼び出し、結果をまとめて返す。
 *
 * エンドポイント: GET /search?q=キーワード&free=1
 * 返り値: { "items": [{ mall, name, price, url, image, shop, free }, ...] }
 *
 * 必要なSecrets(`wrangler secret put <NAME>` で設定。wrangler.tomlには書かない):
 *   RAKUTEN_APP_ID, RAKUTEN_ACCESS_KEY        … 必須(無いと楽天の結果は空)
 *   RAKUTEN_AFFILIATE_ID                       … 任意(紹介料リンク用)
 *   YAHOO_APP_ID                               … 任意(無いとYahoo!の結果は空)
 *   ALLOWED_ORIGIN                             … 任意(未設定なら "*")
 */

const RAKUTEN_API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401";
const YAHOO_API_URL = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch";

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "public, max-age=60",
  };
}

function rakutenReferer(env) {
  return env.SITE_URL || env.RAKUTEN_REFERER || "https://katakanaorijin-byte.github.io/imaure/";
}

async function searchRakuten(env, q, freeOnly) {
  if (!env.RAKUTEN_APP_ID || !env.RAKUTEN_ACCESS_KEY) return [];
  const referer = rakutenReferer(env);
  const params = new URLSearchParams({
    applicationId: env.RAKUTEN_APP_ID,
    accessKey: env.RAKUTEN_ACCESS_KEY,
    format: "json",
    formatVersion: "2",
    keyword: q,
    hits: "20",
    sort: "standard",
    availability: "1",
  });
  if (env.RAKUTEN_AFFILIATE_ID) params.set("affiliateId", env.RAKUTEN_AFFILIATE_ID);
  if (freeOnly) params.set("postageFlag", "1");

  const res = await fetch(`${RAKUTEN_API_URL}?${params.toString()}`, {
    headers: {
      "User-Agent": "yoyaku-radar-search-worker",
      "Referer": referer,
      "Referrer": referer,
      "Origin": referer.replace(/\/+$/, ""),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`rakuten ${res.status}: ${body.slice(0, 500)}`);
  }
  const data = await res.json();
  const rows = data.Items || data.items || [];

  return rows.map((row) => {
    const it = row.Item || row.item || row;
    const imgs = it.mediumImageUrls || it.smallImageUrls || [];
    const first = imgs[0];
    const image = first ? (typeof first === "string" ? first : first.imageUrl) : "";
    return {
      mall: "rakuten",
      name: it.itemName || "",
      price: Number(it.itemPrice) || 0,
      url: it.affiliateUrl || it.itemUrl || "",
      image: image || "",
      shop: it.shopName || "",
      free: it.postageFlag === 1,
    };
  });
}

async function searchYahoo(env, q, freeOnly) {
  if (!env.YAHOO_APP_ID) return [];
  const params = new URLSearchParams({
    appid: env.YAHOO_APP_ID,
    query: q,
    results: "20",
    in_stock: "true",
    condition: "new",
  });

  const res = await fetch(`${YAHOO_API_URL}?${params.toString()}`);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`yahoo ${res.status}: ${body.slice(0, 500)}`);
  }
  const data = await res.json();
  const hits = (data.hits || []).filter((it) => {
    const code = it.shipping && it.shipping.code;
    return freeOnly ? code === 2 : true;
  });

  return hits.map((it) => ({
    mall: "yahoo",
    name: it.name || "",
    price: Number(it.price) || 0,
    url: it.url || "",
    image: (it.image && it.image.medium) || "",
    shop: (it.seller && it.seller.name) || "",
    free: !!(it.shipping && it.shipping.code === 2),
  }));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = env.ALLOWED_ORIGIN || "*";
    const headers = corsHeaders(origin);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers });
    }
    if (url.pathname !== "/search") {
      return new Response("Not found", { status: 404, headers });
    }

    const q = (url.searchParams.get("q") || "").trim();
    if (!q) {
      return new Response(JSON.stringify({ items: [] }), {
        headers: { "Content-Type": "application/json", ...headers },
      });
    }
    const freeOnly = url.searchParams.get("free") === "1";
    const debug = url.searchParams.get("debug") === "1";

    const [rakuten, yahoo] = await Promise.allSettled([
      searchRakuten(env, q, freeOnly),
      searchYahoo(env, q, freeOnly),
    ]);

    const items = []
      .concat(rakuten.status === "fulfilled" ? rakuten.value : [])
      .concat(yahoo.status === "fulfilled" ? yahoo.value : []);

    const payload = { items };
    if (debug) {
      payload.debug = {
        rakuten: rakuten.status === "fulfilled"
          ? { ok: true, count: rakuten.value.length }
          : { ok: false, error: String(rakuten.reason && rakuten.reason.message || rakuten.reason) },
        yahoo: yahoo.status === "fulfilled"
          ? { ok: true, count: yahoo.value.length }
          : { ok: false, error: String(yahoo.reason && yahoo.reason.message || yahoo.reason) },
        hasRakutenAppId: !!env.RAKUTEN_APP_ID,
        hasRakutenAccessKey: !!env.RAKUTEN_ACCESS_KEY,
        hasRakutenAffiliateId: !!env.RAKUTEN_AFFILIATE_ID,
        hasYahooAppId: !!env.YAHOO_APP_ID,
        referer: rakutenReferer(env),
      };
    }

    return new Response(JSON.stringify(payload), {
      headers: { "Content-Type": "application/json", ...headers },
    });
  },
};
