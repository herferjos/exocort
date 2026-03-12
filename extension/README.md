# SecondBrain Extension

Chrome MV3 extension that logs page views and visible text snapshots to the local collector.

## What it does
- Sends `browser.page_view` and `browser.page_text` events to `http://127.0.0.1:8787/events`.
- No audio capture and no microphone permissions.

## Load in Chrome
1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** and select the `extension/` folder
