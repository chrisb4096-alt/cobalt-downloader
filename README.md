# Save Video - Cross-Platform Video Downloader

Download videos from Twitter/X, YouTube, Instagram, Facebook, TikTok, and 15+ more platforms directly to your iPhone's Photos app.

## Quick Install

**On your iPhone**, tap one of these links:

| Shortcut | Description |
|----------|-------------|
| [**Save Video.shortcut**](https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video.shortcut) | Main shortcut - downloads video and saves to Photos |
| [**Save Video (Debug).shortcut**](https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20(Debug).shortcut) | Debug version - shows full API response, copies to clipboard, then downloads |

> If prompted, tap "Allow Untrusted Shortcuts" in Settings > Shortcuts first.

## How It Works

1. **Share** a video link from any app (Twitter, YouTube, etc.) to "Save Video"
2. Or **copy** a video URL and run the shortcut from the Shortcuts app
3. Video downloads at max quality and saves to your Photos

## Architecture

- **Backend**: Self-hosted [cobalt](https://github.com/imputnet/cobalt) v11.5 on Railway
- **Frontend**: iOS Siri Shortcut (Share Sheet + clipboard fallback)
- **API**: `https://cobalt-production-97bf.up.railway.app`

## Supported Platforms

Twitter/X, Instagram, YouTube, Facebook, TikTok, Reddit, Pinterest, Snapchat,
Bluesky, Twitch, SoundCloud, Vimeo, Dailymotion, Tumblr, Bilibili, Loom,
Streamable, OK.ru, Xiaohongshu, Newgrounds, Rutube, VK

## Debugging / Iteration Workflow

If the shortcut doesn't work correctly:

1. Install the **Debug** version from the link above
2. Run it with the problem URL
3. It shows the full API response in Quick Look and **copies it to clipboard**
4. Paste the response into Claude Code (or a new chat) for diagnosis
5. I regenerate the `.shortcut` file, push to this repo, you re-download

### The Iteration Loop

```
iPhone (test) --> clipboard/paste response --> Claude Code (fix)
                                                    |
Claude Code (regenerate .shortcut) --> git push --> iPhone (re-download)
```

To re-download after an update: just tap the install link above again on your iPhone.

### Check Railway Logs

From your PC:
```bash
cd ~/Sideprojects/cobalt-downloader
railway logs
```

## Files

| File | Purpose |
|------|---------|
| `Save Video.shortcut` | Main iOS shortcut (binary plist) |
| `Save Video (Debug).shortcut` | Debug version with response viewer |
| `generate-shortcut.py` | Python script to regenerate both shortcuts |
| `SHORTCUT-GUIDE.md` | Manual build instructions (if you prefer) |

## Regenerating Shortcuts

If you need to change the API URL or key:

1. Edit `API_URL` and `API_KEY` in `generate-shortcut.py`
2. Run: `python generate-shortcut.py`
3. Push: `git add -A && git commit -m "update shortcut" && git push`
4. Re-download on iPhone via the links above

## Sharing with Friends

Send anyone the install link. The API key is embedded, so they can use your
cobalt instance immediately. To revoke access, change the API key on Railway:

```bash
cd ~/Sideprojects/cobalt-downloader
railway variables set API_KEY=$(openssl rand -base64 24)
```

Then regenerate and push the shortcut.
