# Save Video: How We Built a Universal Video Downloader for iPhone

A deep dive into building a one-tap video downloader that works from the iOS Share Sheet for Twitter, YouTube, Instagram, and Facebook -- and the 46 commits it took to get there.

## The Goal

Share a video from any app on your iPhone, tap "Save Video", and it downloads to your Photos. No apps to install, no subscriptions, no ads. Just a Siri Shortcut backed by a self-hosted API.

## Architecture

```
iPhone (Siri Shortcut)
    |
    | POST {url, videoQuality: "max"}
    v
Cobalt Proxy (Node.js, Railway)
    |
    |--- forwards to cobalt for Twitter/YouTube/Instagram/TikTok/etc.
    |--- custom Facebook scraper (cobalt can't handle FB)
    |--- buffers tunnel responses (iOS needs Content-Length)
    v
Cobalt API (Docker, Railway)
    |--- YouTube via residential proxy (Webshare)
    |--- Instagram via session cookies
    |--- Twitter/TikTok/Reddit/20+ others natively
    v
CDN (video file)
    |
    | buffered through proxy with HMAC-signed URL
    v
iPhone saves to Photos
```

Three services, all on Railway:

### 1. Cobalt API (Docker)

[Cobalt](https://github.com/imputnet/cobalt) is an open-source video downloader that supports 20+ platforms through a single POST endpoint. We run a custom Docker image that extends the official one:

```dockerfile
FROM ghcr.io/imputnet/cobalt:latest
USER root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
USER node
ENTRYPOINT ["/entrypoint.sh"]
```

The entrypoint writes Instagram session cookies from an environment variable to a file at runtime -- cobalt reads cookies from a file path, but Railway only supports env vars:

```sh
#!/bin/sh
if [ -n "$COOKIES_JSON" ]; then
    echo "$COOKIES_JSON" > /tmp/cookies.json
    export COOKIE_PATH=/tmp/cookies.json
fi
exec node /app/src/cobalt
```

### 2. Cobalt Proxy (Node.js)

This is where most of the interesting stuff happens. It sits between the iPhone and cobalt, solving three problems that cobalt alone can't:

**Problem 1: Tunnel responses have no Content-Length header.**

Cobalt returns two response types: `redirect` (here's a URL, go download it) and `tunnel` (stream it through cobalt's servers). iOS Shortcuts' "Get Contents of URL" action silently fails on streamed responses without a Content-Length header. YouTube almost always returns `tunnel`.

**Solution:** The proxy rewrites every `tunnel` response to a `redirect` pointing to its own `/buffer` endpoint. The buffer endpoint downloads the entire file into memory, then serves it back with a proper Content-Length header. Buffer URLs are HMAC-signed with a 10-minute expiry so they can't be abused as an open proxy:

```js
function signBufferUrl(tunnelUrl) {
  const exp = Math.floor(Date.now() / 1000) + 600; // 10 min
  const payload = `${tunnelUrl}:${exp}`;
  const sig = crypto.createHmac("sha256", BUFFER_SECRET)
    .update(payload).digest("hex").slice(0, 16);
  return { exp, sig };
}
```

**Problem 2: Cobalt can't download Facebook videos.**

Facebook's video infrastructure is hostile to scrapers. Cobalt returns `error.api.fetch.empty` for every Facebook URL.

**Solution:** The proxy has a 4-strategy Facebook fallback extractor. When cobalt fails on a Facebook URL, it:

1. Tries `web.facebook.com/i/videos/{id}` (international subdomain, less restrictive)
2. Tries the original URL on `web.facebook.com` (for reels/shares)
3. Tries `www.facebook.com/watch/?v={id}` with regex extraction of JSON-escaped CDN URLs from the page source
4. Falls back to `mbasic.facebook.com` (mobile site, SD only but very reliable)

Facebook embeds video URLs in page JSON with escaped slashes (`https:\/\/video.fbcdn.net\/...`), triple-encoded query params (`%5Cu00253D`), and dozens of CDN URL variants scattered across the HTML. The extractor uses 8 regex patterns to find HD/SD URLs, unescapes them, and picks the highest quality:

```js
const FB_VIDEO_REGEXES = [
  { q: "hd", re: /"hd_src_no_ratelimit":"(.*?)"/ },
  { q: "hd", re: /"browser_native_hd_url":"(.*?)"/ },
  { q: "hd", re: /"playable_url_quality_hd":"(.*?)"/ },
  // ... 5 more patterns for HD/SD variants
];
```

All Facebook requests go through a Webshare residential proxy ($3.50/mo) because Facebook blocks datacenter IPs aggressively.

**Problem 3: Instagram carousels return multiple items.**

Cobalt returns `status: "picker"` with an array of URLs for Instagram carousel posts. The proxy rewrites any tunnel URLs in the picker array through the buffer endpoint, same as single videos.

### 3. The iOS Shortcut (Python-generated binary plist)

This is where it got truly painful.

iOS Shortcuts are stored as binary property lists (`.shortcut` files). There's no public documentation for the format. Apple's Shortcuts app builds them through a GUI, but we needed to generate them programmatically because the debug-test-fix loop requires regenerating the shortcut on every iteration:

```
PC: edit Python → generate .shortcut → sign via HubSign → git push
iPhone: open GitHub raw URL in Safari → import shortcut → test → report back
```

We reverse-engineered the format by:
1. Building a working shortcut manually in iOS Shortcuts
2. Extracting it via iCloud link
3. Parsing the binary plist in Python to understand the structure
4. Comparing against a known-working third-party shortcut (TVDL)

#### The Shortcut Format

Every action is a dict with an identifier and parameters:

```python
{
    "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
    "WFWorkflowActionParameters": {
        "UUID": "A1B2C3D4-...",
        "WFURL": "https://...",
        "WFHTTPMethod": "POST",
        "WFHTTPBodyType": "JSON",
        "WFJSONValues": { ... },
    }
}
```

Variables are referenced through UUIDs. When action A produces output and action B needs it, B references A's UUID:

```python
def output_ref(action_uuid, output_name):
    return {
        "Value": {
            "Type": "ActionOutput",
            "OutputUUID": action_uuid,
            "OutputName": output_name,
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }
```

Text interpolation with variables uses a special Unicode replacement character (`\ufffc`) as a placeholder:

```python
def var_text(var_name):
    return {
        "Value": {
            "string": "\ufffc",
            "attachmentsByRange": {
                "{0, 1}": {"Type": "Variable", "VariableName": var_name}
            },
        },
        "WFSerializationType": "WFTextTokenString",
    }
```

#### Signing

iOS 15+ rejects unsigned shortcut files. Apple doesn't provide a public signing API. We use [HubSign](https://hubsign.routinehub.services/sign), a community signing service from RoutineHub, which wraps the shortcut in an Apple Encrypted Archive (AEA1 format):

```python
def sign_shortcut(unsigned_path, signed_path):
    # Multipart form upload to HubSign
    req = urllib.request.Request(
        "https://hubsign.routinehub.services/sign",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    # Returns AEA1-signed shortcut
```

## The 46-Commit Saga

The git log tells the real story. Here's the condensed version.

### Phase 1: Basic Shortcut (commits 1-3)

Got a working shortcut that reads from clipboard, POSTs to cobalt, downloads the video, and saves to Photos. Signed it. Worked for Twitter and YouTube from clipboard. Easy.

### Phase 2: The POST Body Nightmare (commits 4-18)

The shortcut worked when built in the iOS Shortcuts GUI but broke when generated from Python. Same actions, same parameters, but the programmatic version would silently fail on the HTTP POST.

Turns out there are multiple ways to encode an HTTP body in the shortcut format, and only one works: `WFHTTPBodyType: "JSON"` with `WFJSONValues` (a structured dictionary). We tried `WFHTTPBodyType: "File"` first (which is what one reference shortcut used) -- that works for simple POST bodies but mangles JSON encoding.

We built 10+ debug shortcuts that tested individual steps in isolation: POST to httpbin.org to see the raw request, POST without headers, POST with headers, etc. Each debug cycle meant regenerating the shortcut, signing it, pushing to GitHub, downloading on the phone, running it, and reading the result.

### Phase 3: Conditionals (commits 18-22)

iOS Shortcuts conditionals are not what you'd expect. Each if/else/endif is a separate action linked by a `GroupingIdentifier` UUID and a `WFControlFlowMode` (0 = if, 1 = else, 2 = endif). Nested conditionals don't work reliably in programmatic shortcuts. We had to flatten all conditionals into sequential checks with a `handled` flag variable.

The condition format was also undocumented. We discovered that string conditions like `"Contains"` work in some contexts but numeric codes work in others. A reference shortcut (TVDL) used `100` for "Has Any Value" and `4` for "Contains".

### Phase 4: Share Sheet (commits 23-38, the real pain)

Making the shortcut appear in the Share Sheet when you tap "Share" in Twitter/Instagram/YouTube was a multi-week battle.

**What we tried that didn't work:**
- `detect.link` action to extract URLs from shared content (broken in programmatic plists)
- `getitemfromlist` to get the first URL (output name "Item from List" is invalid in programmatic context)
- Various combinations of `WFWorkflowInputContentItemClasses`
- URL type coercion on the Share Sheet input

**What finally worked:** Matching the exact pattern from TVDL (a working third-party shortcut):
- Action 0: `setvariable` from `ExtensionInput` directly (the Share Sheet passes the URL as the extension input)
- `WFWorkflowNoInputBehavior: {Name: "WFWorkflowNoInputBehaviorGetClipboard", Parameters: {}}` (auto-reads clipboard when not launched from Share Sheet)
- `WFWorkflowTypes: ["ActionExtension", "NCWidget", "WatchKit"]` (`ActionExtension` enables the Share Sheet)

This got 3 out of 4 platforms working. Facebook didn't show up in the Share Sheet because Facebook's app shares content as text, not as a URL type. Adding `WFStringContentItem` to `WFWorkflowInputContentItemClasses` fixed that.

### Phase 5: The URL Coercion Problem (commits 39-45)

With Facebook showing in the Share Sheet, we hit the final boss: **the same shortcut can't download videos from all 4 platforms.**

The download URL from the API response is a dictionary value. To use it in a "Get Contents of URL" action, you assign it to a variable. But *how* you assign it matters:

| Method | What it does | Works for |
|--------|-------------|-----------|
| `output_ref_as_url` | Coerces the value to URL type via `WFCoercionVariableAggrandizement` | Twitter, YouTube, Instagram |
| `output_ref` | Raw reference, no type conversion | Facebook, Instagram |
| `output_text` | Wraps in text string (`WFTextTokenString`) | Facebook only |

- **With URL coercion**: Twitter and YouTube work, but Facebook's 1100+ character CDN URLs with triple-encoded query parameters get mangled by the coercion.
- **Without URL coercion**: Facebook works, but Twitter and YouTube's proxy buffer URLs (shorter, simpler) fail silently -- the download action apparently needs URL-typed input for these.
- **With text wrapping**: Instagram breaks entirely with "make sure to pass a valid url".

**The solution:** Platform detection inside the shortcut. Before downloading, check if the original `videoURL` contains "facebook". If yes, use raw reference (no coercion). If no, use URL coercion.

```python
# Facebook URLs break with URL coercion, everything else needs it
actions.append(act("getvariable", {"WFVariable": var_ref("videoURL")}))
actions.append(if_begin(g_facebook, "Contains", "facebook"))

# Facebook path: no URL coercion
actions.append(act("setvariable", {
    "WFVariableName": "downloadURL",
    "WFInput": output_ref(geturl_uuid, "Dictionary Value"),  # raw
}))
# ... download and save ...

actions.append(if_else(g_facebook))

# Default path: URL coercion (Twitter, YouTube, Instagram)
actions.append(act("setvariable", {
    "WFVariableName": "downloadURL",
    "WFInput": output_ref_as_url(geturl_uuid, "Dictionary Value"),  # coerced
}))
# ... download and save ...

actions.append(if_end(g_facebook))
```

### Phase 6: Done (commit 46)

Added `.gitignore` and rate limiting (20 req/min per IP) to the proxy. All 4 platforms work from the Share Sheet. Ship it.

## The Final Shortcut Flow

```
1. User taps Share → Save Video (or runs manually, reads clipboard)
2. Set videoURL = Share Sheet input
3. Show notification: "Downloading..."
4. POST to proxy: {url: videoURL, videoQuality: "max", youtubeVideoCodec: "h264"}
5. Extract status from response
6. If status = "error" → show alert, stop
7. If status = "picker" (Instagram carousel):
   a. Loop through picker array
   b. For each item: download URL (with URL coercion) → save to Photos
   c. Show "All items saved!"
8. If status = "redirect" (single video):
   a. If videoURL contains "facebook":
      - Set downloadURL WITHOUT URL coercion
   b. Else:
      - Set downloadURL WITH URL coercion
   c. Download → save to Photos → "Video saved!"
```

## What I Learned

1. **iOS Shortcuts are binary plists with zero documentation.** The only way to understand the format is to build working shortcuts in the GUI, export them, and reverse-engineer the structure. Different actions have subtly different parameter requirements that are nowhere to be found online.

2. **The iteration loop is brutal.** Every change means: edit Python on PC → generate binary plist → sign via API → git push → open URL on iPhone → import → test → read result → repeat. There's no simulator, no debugger, no error messages beyond "there was a problem running your shortcut."

3. **Type coercion in Shortcuts is a hidden minefield.** The same action (`Get Contents of URL`) silently succeeds or fails based on whether the input variable was coerced to URL type, left as raw, or wrapped in text. Different platforms produce URLs with different characteristics (length, encoding, structure) that interact with coercion differently. This is not documented anywhere.

4. **Facebook is a special snowflake in every possible way.** It shares as text instead of URL. Its video CDN URLs are 1100+ characters with triple-encoded query params. Cobalt can't extract them at all. The page HTML has video URLs scattered across JSON blobs with escaped slashes. And it blocks datacenter IPs, requiring a residential proxy.

5. **Cobalt's tunnel vs redirect distinction matters more than you'd think.** YouTube returns tunnel (streamed, no Content-Length), Twitter returns redirect (direct CDN URL). iOS Shortcuts silently fails on streamed responses. A buffering proxy with signed URLs solved this cleanly.

## Cost

- Railway: ~$5/month (two small services + one custom Docker container)
- Webshare residential proxy: $3.50/month
- HubSign: free
- Total: ~$8.50/month for unlimited video downloads from 20+ platforms
