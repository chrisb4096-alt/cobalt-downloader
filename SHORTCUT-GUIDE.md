# Save Video - iOS Siri Shortcut Setup Guide

## Your Cobalt Instance
- **API URL**: `https://cobalt-production-97bf.up.railway.app`
- **API Key**: `JacAZJQQjLUsUjjqZCedjJQOJFfqhwYG`
- **Railway Project**: `cobalt-downloader`
- **Railway Dashboard**: https://railway.com/project/df21ee4f-16e0-4d2a-baf4-84d878625586

## Supported Platforms
Twitter/X, Instagram, YouTube, Facebook, TikTok, Reddit, Pinterest, Snapchat,
Bluesky, Twitch, SoundCloud, Vimeo, Dailymotion, Tumblr, Bilibili, Loom, and more.

---

## Build the Shortcut (Step-by-Step)

Open **Shortcuts app** > tap **+** (top right) > name it **"Save Video"**

### 1. Configure Share Sheet Input

Tap the **info (i) button** at the bottom or the shortcut name at top:
- Tap **"Anything"** under "Receives" and select: **URLs**, **Text**
- Toggle **"Show in Share Sheet"** ON
- Set icon to a blue arrow.down.circle if you like

### 2. Add Actions (in exact order)

---

#### Action 1: Receive Input
This is automatic -- the "Shortcut Input" is already available when shared.

---

#### Action 2: If (check for input)

Add: **If**
- Input: `Shortcut Input`
- Condition: `has any value`

---

#### Action 3: Set Variable (from share sheet)

Inside the "If" block, add: **Set Variable**
- Variable Name: `videoURL`
- Value: `Shortcut Input`

---

#### Action 4: Otherwise (clipboard fallback)

In the **Otherwise** section:

Add: **Get Clipboard**

Then add: **Set Variable**
- Variable Name: `videoURL`
- Value: `Clipboard`

---

#### Action 5: End If

(Auto-added when you add the If)

---

#### Action 6: Get Contents of URL (API call)

Add: **Get Contents of URL**
- URL: `https://cobalt-production-97bf.up.railway.app/`
- Show More:
  - Method: **POST**
  - Headers (add 3):
    - `Accept` = `application/json`
    - `Content-Type` = `application/json`
    - `Authorization` = `Api-Key JacAZJQQjLUsUjjqZCedjJQOJFfqhwYG`
  - Request Body: **JSON**
    - Add these keys:
      - `url` (Text) = `videoURL` variable
      - `videoQuality` (Text) = `max`
      - `filenameStyle` (Text) = `pretty`
      - `youtubeVideoCodec` (Text) = `h264`

---

#### Action 7: Set Variable for API response

Add: **Set Variable**
- Variable Name: `apiResponse`
- Value: `Contents of URL`

---

#### Action 8: Get status from response

Add: **Get Dictionary Value**
- Get: `Value` for `Key`: `status`
- From: `apiResponse`

Add: **Set Variable**
- Variable Name: `status`
- Value: `Dictionary Value`

---

#### Action 9: If status = redirect or tunnel

Add: **If**
- Input: `status`
- Condition: `contains` `tunnel`

  Inside this If block:

  a. **Get Dictionary Value**
     - Get: `Value` for `Key`: `url`
     - From: `apiResponse`

  b. **Get Contents of URL**
     - URL: `Dictionary Value` (the download URL from step a)
     - (leave as GET, no headers needed)

  c. **Save to Photo Album**
     - Input: `Contents of URL`
     - Album: `Recents`

  d. **Show Notification**
     - Title: `Save Video`
     - Body: `Video saved!`

---

#### Action 10: Otherwise (handle picker or redirect)

In the **Otherwise** section:

Add a nested **If**:
- Input: `status`
- Condition: `contains` `picker`

  Inside this nested If:

  a. **Get Dictionary Value**
     - Get: `Value` for `Key`: `picker`
     - From: `apiResponse`

  b. **Get Item from List**
     - Get: `First Item`
     - From: `Dictionary Value`

  c. **Get Dictionary Value**
     - Get: `Value` for `Key`: `url`
     - From: `Item from List`

  d. **Get Contents of URL**
     - URL: `Dictionary Value`

  e. **Save to Photo Album**
     - Input: `Contents of URL`
     - Album: `Recents`

  f. **Show Notification**
     - Title: `Save Video`
     - Body: `Video saved!`

---

#### Action 11: Otherwise (handle redirect status)

In the second **Otherwise** section:

Add another nested **If**:
- Input: `status`
- Condition: `contains` `redirect`

  Inside:

  a. **Get Dictionary Value**
     - Get: `Value` for `Key`: `url`
     - From: `apiResponse`

  b. **Get Contents of URL**
     - URL: `Dictionary Value`

  c. **Save to Photo Album**
     - Input: `Contents of URL`
     - Album: `Recents`

  d. **Show Notification**
     - Title: `Save Video`
     - Body: `Video saved!`

---

#### Action 12: Otherwise (error handling)

Final **Otherwise**:

  a. **Get Dictionary Value**
     - Get: `Value` for `Key`: `error`
     - From: `apiResponse`

  b. **Show Alert**
     - Title: `Download Failed`
     - Message: `Dictionary Value`

---

#### Close all End Ifs

Make sure all If/Otherwise/End If blocks are properly closed.

---

## Simplified Alternative (Fewer Actions)

If the nested If/Otherwise is too complex, here's a simpler version that
handles the most common case (tunnel) and falls back to showing an error:

```
1. Receive Shortcut Input (URLs, Text)
2. If Shortcut Input has any value
     Set Variable "videoURL" to Shortcut Input
   Otherwise
     Get Clipboard
     Set Variable "videoURL" to Clipboard
   End If
3. Get Contents of URL
     POST https://cobalt-production-97bf.up.railway.app/
     Headers: Accept=application/json, Content-Type=application/json,
              Authorization=Api-Key JacAZJQQjLUsUjjqZCedjJQOJFfqhwYG
     Body JSON: {"url": videoURL, "videoQuality": "max",
                 "filenameStyle": "pretty", "youtubeVideoCodec": "h264"}
4. Set Variable "apiResponse" to Contents of URL
5. Get Dictionary Value for key "status" from apiResponse
6. If Dictionary Value contains "error"
     Get Dictionary Value for key "error" from apiResponse
     Show Alert "Download failed: [error]"
   Otherwise
     Get Dictionary Value for key "url" from apiResponse
     Get Contents of URL (the download URL)
     Save to Photo Album "Recents"
     Show Notification "Video saved!"
   End If
```

This works because both `tunnel` and `redirect` responses have a `url` field.
The only edge case it misses is `picker` (used for Instagram carousels with
multiple items) -- it will just download the first item's URL which is usually
what you want.

---

## Share with Friends

1. Long-press **"Save Video"** in the Shortcuts app
2. Tap **Share** > **Copy iCloud Link**
3. Send that link to friends
4. They install and it works immediately (API key is embedded)

**Note**: Anyone with the shortcut can use your cobalt instance. This is fine
for a small group. To revoke access later, change `API_KEY` on Railway:
```
railway variables set API_KEY=<new-key>
```

---

## Testing Checklist

Test with these URLs after building the shortcut:

- [ ] **YouTube**: https://www.youtube.com/watch?v=dQw4w9WgXcQ
- [ ] **Twitter/X**: Share a tweet with video from the X app
- [ ] **Instagram**: Share a reel from the Instagram app
- [ ] **Facebook**: Share a video from the Facebook app
- [ ] **TikTok**: Share a TikTok video
- [ ] **Clipboard fallback**: Copy a video URL, open Shortcuts, run "Save Video"

---

## Troubleshooting

### "Download failed" error
- Check the URL is a direct link to a video post (not a profile page)
- Some private/age-restricted content may not work
- Instagram stories require cookies (not configured by default)

### Shortcut doesn't appear in Share Sheet
- Go to shortcut settings > ensure "Show in Share Sheet" is ON
- Restart your phone if it still doesn't appear

### Railway instance down
- Check https://railway.com/project/df21ee4f-16e0-4d2a-baf4-84d878625586
- Or run: `cd ~/Sideprojects/cobalt-downloader && railway service status`

### Regenerate API Key
```bash
cd ~/Sideprojects/cobalt-downloader
railway variables set API_KEY=$(openssl rand -base64 24)
```
Then update the key in your shortcut.

---

## Optional: Audio-Only Shortcut

Duplicate "Save Video" and change the JSON body to:
```json
{
  "url": videoURL,
  "downloadMode": "audio",
  "audioFormat": "mp3",
  "audioBitrate": "320",
  "filenameStyle": "pretty"
}
```
Name it "Save Audio" for downloading music/podcasts.

---

## Cost
~$2-5/month on Railway depending on usage. The cobalt Docker image is lightweight
and only runs when processing requests (Railway's usage-based billing).
