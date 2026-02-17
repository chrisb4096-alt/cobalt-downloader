const http = require("http");
const crypto = require("crypto");
const { ProxyAgent } = require("undici");

const COBALT_URL = process.env.COBALT_URL;
const BUFFER_SECRET = process.env.BUFFER_SECRET;
const FACEBOOK_COOKIES = process.env.FACEBOOK_COOKIES || "";
const HTTP_PROXY = process.env.HTTP_PROXY || "";
const PORT = process.env.PORT || 3000;

// Create proxy dispatcher for Facebook requests (residential IP)
const proxyDispatcher = HTTP_PROXY ? new ProxyAgent(HTTP_PROXY) : undefined;

if (!COBALT_URL || !BUFFER_SECRET) {
  console.error("Required env vars: COBALT_URL, BUFFER_SECRET");
  process.exit(1);
}

function signBufferUrl(tunnelUrl) {
  const exp = Math.floor(Date.now() / 1000) + 600;
  const payload = `${tunnelUrl}:${exp}`;
  const sig = crypto
    .createHmac("sha256", BUFFER_SECRET)
    .update(payload)
    .digest("hex")
    .slice(0, 16);
  return { exp, sig };
}

function verifyBufferUrl(tunnelUrl, exp, sig) {
  if (Math.floor(Date.now() / 1000) > Number(exp)) return false;
  const payload = `${tunnelUrl}:${exp}`;
  const expected = crypto
    .createHmac("sha256", BUFFER_SECRET)
    .update(payload)
    .digest("hex")
    .slice(0, 16);
  return sig === expected;
}

// --- Facebook fallback extractor ---

const FB_URL_PATTERNS = [
  /facebook\.com\/(?:watch\/?\?v=|reel\/|share\/(?:v|r)\/|.*\/videos\/)(\d+)/,
  /facebook\.com\/.*\/posts\/(\d+)/,
  /fb\.watch\//,
];

function isFacebookUrl(url) {
  return FB_URL_PATTERNS.some((p) => p.test(url));
}

function extractFbVideoId(url) {
  const patterns = [
    /\/videos\/(\d+)/,
    /[?&]v=(\d+)/,
    /\/reel\/(\d+)/,
    /\/share\/(?:v|r)\/(\d+)/,
    /\/watch\/?\?v=(\d+)/,
    /story_fbid=(\d+)/,
  ];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1];
  }
  return null;
}

const FB_VIDEO_REGEXES = [
  { q: "hd", re: /"hd_src_no_ratelimit":"(.*?)"/ },
  { q: "hd", re: /"browser_native_hd_url":"(.*?)"/ },
  { q: "hd", re: /"playable_url_quality_hd":"(.*?)"/ },
  { q: "hd", re: /"hd_src":"(.*?)"/ },
  { q: "sd", re: /"sd_src_no_ratelimit":"(.*?)"/ },
  { q: "sd", re: /"browser_native_sd_url":"(.*?)"/ },
  { q: "sd", re: /"playable_url":"(.*?)"/ },
  { q: "sd", re: /"sd_src":"(.*?)"/ },
];

function unescapeFbUrl(encoded) {
  if (!encoded) return null;
  try {
    return JSON.parse(`"${encoded}"`);
  } catch {
    return encoded.replace(/\\\//g, "/").replace(/\\u0025/g, "%");
  }
}

function parseVideoUrls(html) {
  let hd = null,
    sd = null;
  for (const { q, re } of FB_VIDEO_REGEXES) {
    const m = html.match(re);
    if (m && m[1]) {
      const url = unescapeFbUrl(m[1]);
      if (url && url.startsWith("http")) {
        if (q === "hd" && !hd) hd = url;
        if (q === "sd" && !sd) sd = url;
      }
    }
  }
  return { hd, sd };
}

const BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  Accept:
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.5",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "none",
};

async function resolveFbShortLink(url) {
  if (!url.includes("fb.watch")) return url;
  try {
    const opts = { redirect: "manual" };
    if (proxyDispatcher) opts.dispatcher = proxyDispatcher;
    const resp = await fetch(url, opts);
    const loc = resp.headers.get("location");
    return loc || url;
  } catch {
    return url;
  }
}

async function extractFacebookVideo(originalUrl) {
  let url = await resolveFbShortLink(originalUrl);
  const videoId = extractFbVideoId(url);
  if (!videoId) {
    console.log(`[fb] Could not extract video ID from: ${url}`);
    return null;
  }
  console.log(`[fb] Extracting video ID: ${videoId}`);

  const headers = { ...BROWSER_HEADERS };
  if (FACEBOOK_COOKIES) headers["Cookie"] = FACEBOOK_COOKIES;

  const fetchOpts = (h) => {
    const opts = { headers: h, redirect: "follow" };
    if (proxyDispatcher) opts.dispatcher = proxyDispatcher;
    return opts;
  };

  // Strategy 1: web.facebook.com/i/videos
  try {
    const resp = await fetch(
      `https://web.facebook.com/i/videos/${videoId}`,
      fetchOpts(headers)
    );
    const html = await resp.text();
    console.log(`[fb] web.facebook.com status=${resp.status} len=${html.length}`);
    const urls = parseVideoUrls(html);
    if (urls.hd || urls.sd) {
      console.log(`[fb] Found via web.facebook.com (HD: ${!!urls.hd})`);
      return urls.hd || urls.sd;
    }
  } catch (e) {
    console.log(`[fb] web.facebook.com failed: ${e.message}`);
  }

  // Strategy 2: original URL on web.facebook.com
  try {
    const webUrl = url.replace("www.facebook.com", "web.facebook.com");
    const resp = await fetch(webUrl, fetchOpts(headers));
    const html = await resp.text();
    console.log(`[fb] web reel status=${resp.status} len=${html.length}`);
    const urls = parseVideoUrls(html);
    if (urls.hd || urls.sd) {
      console.log(`[fb] Found via web reel URL (HD: ${!!urls.hd})`);
      return urls.hd || urls.sd;
    }
  } catch (e) {
    console.log(`[fb] web reel URL failed: ${e.message}`);
  }

  // Strategy 3: www.facebook.com/watch
  try {
    const resp = await fetch(
      `https://www.facebook.com/watch/?v=${videoId}`,
      fetchOpts(headers)
    );
    const html = await resp.text();
    // Debug: check what video-related patterns exist
    const patterns = {
      fbcdn_mp4: (html.match(/fbcdn\.net[^"'\s]*\.mp4/g) || []).length,
      browser_native: (html.match(/browser_native/g) || []).length,
      playable_url: (html.match(/playable_url/g) || []).length,
      video_url: (html.match(/"video_url"/g) || []).length,
      hd_src: (html.match(/hd_src/g) || []).length,
      sd_src: (html.match(/sd_src/g) || []).length,
    };
    console.log(`[fb] www watch status=${resp.status} len=${html.length} patterns=${JSON.stringify(patterns)}`);
    const urls = parseVideoUrls(html);
    if (urls.hd || urls.sd) {
      console.log(`[fb] Found via www.facebook.com/watch (HD: ${!!urls.hd})`);
      return urls.hd || urls.sd;
    }
    // Try broader patterns - Facebook encodes URLs with escaped slashes in JSON
    const fbcdnAll = html.match(/https?:[\\\/]+[a-z0-9-]+\.fbcdn\.net[^"'\s\\]*\.mp4[^"'\s\\]*/g);
    // Extract all escaped video CDN URLs from the page JSON
    const escapedAll = [];
    const escapedRe = /"(https?:\\\/\\\/[^"]*?\.fbcdn\.net[^"]*?\.mp4[^"]*)"/g;
    let em;
    while ((em = escapedRe.exec(html)) !== null) {
      escapedAll.push(em[1].replace(/\\\//g, '/'));
    }
    if (escapedAll.length > 0) {
      // Prefer HD: look for urls with higher bitrate or "hd" markers
      const hdUrl = escapedAll.find(u => /sve_hd|quality_hd|hd_src/i.test(u));
      const best = hdUrl || escapedAll.sort((a, b) => {
        const brA = (a.match(/bitrate=(\d+)/) || [])[1] || 0;
        const brB = (b.match(/bitrate=(\d+)/) || [])[1] || 0;
        return Number(brB) - Number(brA);
      })[0];
      console.log(`[fb] Found ${escapedAll.length} CDN URLs, using: ${best.slice(0, 100)}...`);
      return best;
    }
    if (fbcdnAll && fbcdnAll.length > 0) {
      const best = fbcdnAll.sort((a, b) => b.length - a.length)[0];
      const url = best.replace(/\\\//g, '/');
      console.log(`[fb] Found ${fbcdnAll.length} unescaped CDN URLs, using: ${url.slice(0, 100)}...`);
      return url;
    }
  } catch (e) {
    console.log(`[fb] www.facebook.com/watch failed: ${e.message}`);
  }

  // Strategy 4: mbasic.facebook.com (SD only, but reliable for public)
  try {
    const mHeaders = {
      ...headers,
      "User-Agent":
        "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
    };
    const resp = await fetch(
      `https://mbasic.facebook.com/video/redirect/?src=${videoId}`,
      fetchOpts(mHeaders)
    );
    const html = await resp.text();
    console.log(`[fb] mbasic status=${resp.status} len=${html.length}`);
    const mbasicLink = html.match(
      /href="(https:\/\/video[^"]+\.mp4[^"]*)"/
    );
    if (mbasicLink) {
      const sdUrl = mbasicLink[1].replace(/&amp;/g, "&");
      console.log(`[fb] Found via mbasic.facebook.com (SD)`);
      return sdUrl;
    }
  } catch (e) {
    console.log(`[fb] mbasic.facebook.com failed: ${e.message}`);
  }

  console.log(`[fb] All strategies exhausted for video ${videoId}`);
  return null;
}

// --- Server ---

const server = http.createServer(async (req, res) => {
  // Health check
  if (req.method === "GET" && (req.url === "/" || req.url === "/health")) {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("ok");
    return;
  }

  // Buffer endpoint - downloads content, serves with Content-Length
  if (req.method === "GET" && req.url.startsWith("/buffer?")) {
    const params = new URL(req.url, `http://localhost:${PORT}`).searchParams;
    const targetUrl = params.get("url");
    const exp = params.get("exp");
    const sig = params.get("sig");

    if (!targetUrl || !exp || !sig) {
      res.writeHead(400, { "Content-Type": "text/plain" });
      res.end("Missing parameters");
      return;
    }

    if (!verifyBufferUrl(targetUrl, exp, sig)) {
      res.writeHead(403, { "Content-Type": "text/plain" });
      res.end("Invalid or expired signature");
      return;
    }

    // Allow fetching from cobalt OR Facebook CDN (for fb fallback)
    const cobaltHost = new URL(COBALT_URL).hostname;
    const isCobalt = targetUrl.includes(cobaltHost);
    const isFbCdn =
      targetUrl.includes("fbcdn.net") || targetUrl.includes("facebook.com");
    if (!isCobalt && !isFbCdn) {
      res.writeHead(403, { "Content-Type": "text/plain" });
      res.end("Forbidden");
      return;
    }

    try {
      console.log(`[buffer] Downloading: ${targetUrl.slice(0, 80)}...`);
      const dlHeaders = {};
      if (isFbCdn)
        dlHeaders["User-Agent"] = "facebookexternalhit/1.1";

      const response = await fetch(targetUrl, { headers: dlHeaders });

      if (!response.ok) {
        res.writeHead(502, { "Content-Type": "text/plain" });
        res.end(`Upstream returned ${response.status}`);
        return;
      }

      const buffer = Buffer.from(await response.arrayBuffer());
      console.log(
        `[buffer] Buffered ${(buffer.length / 1024 / 1024).toFixed(1)}MB`
      );

      const headers = {
        "Content-Type": response.headers.get("content-type") || "video/mp4",
        "Content-Length": buffer.length,
      };
      const cd = response.headers.get("content-disposition");
      if (cd) headers["Content-Disposition"] = cd;

      res.writeHead(200, headers);
      res.end(buffer);
    } catch (err) {
      console.error("[buffer] Error:", err.message);
      res.writeHead(502, { "Content-Type": "text/plain" });
      res.end("Buffer download failed");
    }
    return;
  }

  // API proxy - forward POST to cobalt, with Facebook fallback
  if (req.method === "POST" && req.url === "/") {
    let body = "";
    for await (const chunk of req) body += chunk;

    let parsed;
    try {
      parsed = JSON.parse(body);
    } catch {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "error", error: { code: "error.proxy.bad_request" } }));
      return;
    }

    try {
      const headers = {
        "Content-Type": "application/json",
        Accept: "application/json",
      };
      if (req.headers.authorization) {
        headers.Authorization = req.headers.authorization;
      }

      const response = await fetch(COBALT_URL, {
        method: "POST",
        headers,
        body,
      });

      const data = await response.json();
      const proxyOrigin = `https://${req.headers.host}`;

      // Facebook fallback: if cobalt fails and it's a Facebook URL
      if (
        data.status === "error" &&
        data.error?.code === "error.api.fetch.empty" &&
        parsed.url &&
        isFacebookUrl(parsed.url)
      ) {
        console.log(`[proxy] Cobalt failed for Facebook, trying fallback...`);
        const fbUrl = await extractFacebookVideo(parsed.url);
        if (fbUrl) {
          // Buffer FB video through signed URL (FB CDN URLs expire)
          const { exp, sig } = signBufferUrl(fbUrl);
          const bufferUrl = `${proxyOrigin}/buffer?url=${encodeURIComponent(fbUrl)}&exp=${exp}&sig=${sig}`;
          console.log(`[proxy] Facebook fallback success`);
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(
            JSON.stringify({
              status: "redirect",
              url: bufferUrl,
              filename: `facebook_${extractFbVideoId(parsed.url) || "video"}.mp4`,
            })
          );
          return;
        }
        console.log(`[proxy] Facebook fallback also failed`);
      }

      // Rewrite tunnel → redirect through signed buffer endpoint
      if (data.status === "tunnel" && data.url) {
        console.log(
          `[proxy] Rewriting tunnel for: ${data.filename || "unknown"}`
        );
        const { exp, sig } = signBufferUrl(data.url);
        data.status = "redirect";
        data.url = `${proxyOrigin}/buffer?url=${encodeURIComponent(data.url)}&exp=${exp}&sig=${sig}`;
      }

      // Rewrite picker items that use tunnel
      if (data.status === "picker" && data.picker) {
        for (const item of data.picker) {
          if (item.url && item.url.includes("/tunnel")) {
            const { exp, sig } = signBufferUrl(item.url);
            item.url = `${proxyOrigin}/buffer?url=${encodeURIComponent(item.url)}&exp=${exp}&sig=${sig}`;
          }
        }
      }

      console.log(
        `[proxy] ${data.status}: ${data.filename || data.error?.code || ""}`
      );
      res.writeHead(response.status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
    } catch (err) {
      console.error("[proxy] Error:", err.message);
      res.writeHead(502, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          status: "error",
          error: { code: "error.proxy.fail" },
        })
      );
    }
    return;
  }

  res.writeHead(404);
  res.end("Not found");
});

server.listen(PORT, () => console.log(`Proxy running on :${PORT}`));
