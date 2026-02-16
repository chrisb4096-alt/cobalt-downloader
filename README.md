# Save Video - Cross-Platform Video Downloader

Download videos from Twitter/X, YouTube, Instagram, Facebook, TikTok, and 15+ more platforms directly to your iPhone's Photos app.

## Quick Install

**On your iPhone**, open Safari and tap one of these links:

| Shortcut | Description |
|----------|-------------|
| [**Save Video (Signed)**](https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20(Signed).shortcut) | Main shortcut - downloads video, saves to Photos |
| [**Save Video Debug (Signed)**](https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20Debug%20(Signed).shortcut) | Debug version - shows full API response + copies to clipboard |

These are **Apple-signed** `.shortcut` files (AEA format) -- they import directly on iOS 15+ without needing "Allow Untrusted Shortcuts".

## How It Works

1. **Share** a video link from any app (Twitter, YouTube, etc.) to "Save Video"
2. Or **copy** a video URL and run the shortcut from the Shortcuts app
3. Video downloads at max quality and saves to your Photos

## Architecture

- **Backend**: Self-hosted [cobalt](https://github.com/imputnet/cobalt) v11.5 on Railway
- **Frontend**: iOS Siri Shortcut (Share Sheet + clipboard fallback)
- **API**: `https://cobalt-production-97bf.up.railway.app`
- **Signing**: [RoutineHub HubSign](https://hubsign.routinehub.services/sign) service

## Supported Platforms

Twitter/X, Instagram, YouTube, Facebook, TikTok, Reddit, Pinterest, Snapchat,
Bluesky, Twitch, SoundCloud, Vimeo, Dailymotion, Tumblr, Bilibili, Loom,
Streamable, OK.ru, Xiaohongshu, Newgrounds, Rutube, VK

## Debugging / Iteration Workflow

If the shortcut doesn't work correctly:

1. Install the **Debug (Signed)** version from the link above
2. Run it with the problem URL
3. It shows the full API response in Quick Look and **copies it to clipboard**
4. Paste the response into Claude Code (or a new chat) for diagnosis
5. I regenerate + re-sign the `.shortcut` file, push to this repo
6. You tap the install link again on your iPhone

### The Iteration Loop

```
iPhone (test) --> clipboard/paste response --> Claude Code (fix)
                                                    |
Claude Code (regenerate + sign) --> git push --> iPhone (re-download)
```

### Check Railway Logs

From your PC:
```bash
cd ~/Sideprojects/cobalt-downloader
railway logs
```

## Files

| File | Purpose |
|------|---------|
| `Save Video (Signed).shortcut` | Main shortcut, Apple-signed (AEA) |
| `Save Video Debug (Signed).shortcut` | Debug shortcut, Apple-signed (AEA) |
| `Save Video.shortcut` | Unsigned plist (source) |
| `Save Video (Debug).shortcut` | Unsigned debug plist (source) |
| `generate-shortcut.py` | Python script to generate, sign, and output all shortcuts |
| `SHORTCUT-GUIDE.md` | Manual build instructions (fallback) |

## Regenerating Shortcuts

If you need to change the API URL or key:

1. Edit `API_URL` and `API_KEY` in `generate-shortcut.py`
2. Run: `python generate-shortcut.py` (auto-generates + signs via HubSign)
3. Push: `git add -A && git commit -m "update shortcut" && git push`
4. Re-download on iPhone via the links above

## Sharing with Friends

Send anyone the signed install link. The API key is embedded, so they can use
your cobalt instance immediately. To revoke access, change the API key on Railway:

```bash
cd ~/Sideprojects/cobalt-downloader
railway variables set API_KEY=$(openssl rand -base64 24)
```

Then regenerate and push the shortcut.
