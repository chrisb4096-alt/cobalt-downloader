const http = require("http");
const crypto = require("crypto");

const COBALT_URL = process.env.COBALT_URL;
const BUFFER_SECRET = process.env.BUFFER_SECRET;
const PORT = process.env.PORT || 3000;

if (!COBALT_URL || !BUFFER_SECRET) {
  console.error("Required env vars: COBALT_URL, BUFFER_SECRET");
  process.exit(1);
}

// HMAC-sign a buffer URL so only this proxy can generate valid links
function signBufferUrl(tunnelUrl) {
  const exp = Math.floor(Date.now() / 1000) + 600; // 10 min expiry
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

const server = http.createServer(async (req, res) => {
  // Health check
  if (req.method === "GET" && (req.url === "/" || req.url === "/health")) {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("ok");
    return;
  }

  // Buffer endpoint - downloads tunnel content, serves with Content-Length
  // Protected by HMAC signature so only proxy-generated URLs work
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

    // Verify HMAC signature and expiration
    if (!verifyBufferUrl(targetUrl, exp, sig)) {
      res.writeHead(403, { "Content-Type": "text/plain" });
      res.end("Invalid or expired signature");
      return;
    }

    // Only allow fetching from our cobalt instance
    const cobaltHost = new URL(COBALT_URL).hostname;
    if (!targetUrl.includes(cobaltHost)) {
      res.writeHead(403, { "Content-Type": "text/plain" });
      res.end("Forbidden");
      return;
    }

    try {
      console.log(`[buffer] Downloading: ${targetUrl.slice(0, 80)}...`);
      const response = await fetch(targetUrl);

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

  // API proxy - forward POST to cobalt, rewrite tunnel URLs
  if (req.method === "POST" && req.url === "/") {
    let body = "";
    for await (const chunk of req) body += chunk;

    try {
      const headers = {
        "Content-Type": "application/json",
        Accept: "application/json",
      };
      // Forward the API key - cobalt validates it
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
