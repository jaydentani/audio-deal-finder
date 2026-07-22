# Audio Deal Finder Bot

Modular rewrite of the original single-file `bot.py`. Same zero-cost,
zero-proxy philosophy (plain `requests` + RSS/JSON, no headless browsers,
no paid infra) -- just restructured for maintainability and the four
issues you flagged.

## What changed

### 1. Keyword & price matching (`matching.py`, `config.py`)
- **Negative keywords**: a global list (`wanted`, `wtb`, `box only`,
  `broken`, `for parts`, etc. -- see `config.GLOBAL_NEGATIVE_KEYWORDS`)
  is checked first and rejects the listing outright. Each watchlist
  entry can also carry its own extra negatives (e.g. `"sierra"` excludes
  `"jeep"`/`"fiat"`/`"car"`/`"truck"` to avoid vehicle listings).
- **Price fallback chain**: `extract_price()` tries `$750` style first,
  then `USD 750`, then `"700 shipped"` / `"obo"` / `"firm"` patterns,
  then a bare 3-5 digit number as a last resort -- with a sanity bound
  (1-50,000) so it doesn't grab a year or phone number fragment.

### 2. New feed sources (`feeds/`)
- `feeds/usaudiomart.py` -- the original RSS source, unchanged behavior.
- `feeds/reddit_avexchange.py` -- pulls r/AVexchange via Reddit's public
  `.json` endpoint. **Set a real `REDDIT_USER_AGENT` in `config.py`**
  (include your Reddit username) or Reddit will 429 you fast.
- `feeds/craigslist.py` -- uses Craigslist's `&format=rss` search
  export, one request per (region, watchlist keyword) pair, throttled by
  `CRAIGSLIST_REQUEST_DELAY_SECONDS`. Configure regions in
  `config.CRAIGSLIST_REGIONS`.
- Adding a new source later = write a module with a `fetch()` function
  returning the standard listing dict shape, then register it in
  `feeds/__init__.py`.

### 3. Storage / git bloat (`storage.py`, `.github/workflows/main.yml`)
The old workflow committed `seen_listings.json` to the repo on every run
forever, bloating git history for what's really just cache state.

- `storage.py` is now storage-agnostic -- it just reads/writes a JSON
  file path. It has no idea whether it's running in CI or on your Mac.
- On GitHub Actions, the workflow now uses `actions/cache` instead of
  `git commit && git push`. The cache key includes `github.run_id` (a
  fixed key wouldn't work -- GitHub Actions cache entries are immutable,
  so the exact same key never re-saves) with a prefix `restore-keys`
  fallback to pull the most recent prior run's file. **No commits, no
  git bloat, no `[skip ci]` dance required.**
- On your Mac: nothing to configure. `seen_listings.json` just sits next
  to `bot.py` on disk, updated in place by every `launchd`/`cron` run.

### 4. Code structure
```
audio_deal_finder/
├── bot.py                 # orchestration entrypoint (run this)
├── config.py               # watchlist, negative keywords, feed settings
├── matching.py              # price extraction + keyword matching
├── storage.py               # seen_listings.json read/write
├── notifier.py               # Discord webhook sender
├── feeds/
│   ├── __init__.py            # ACTIVE_FEEDS registry
│   ├── base.py                  # shared HTTP helper
│   ├── usaudiomart.py
│   ├── reddit_avexchange.py
│   └── craigslist.py
└── .github/workflows/main.yml
```
Logging replaces `print()` throughout (`logging.basicConfig` in
`bot.py`), each feed module fails independently (one bad source can't
crash the whole scan), and everything is PEP-8 formatted.

## Migrating to a Mac (`launchd`)

Nothing in `bot.py`/`storage.py` needs to change. Just:

1. `pip install requests` locally (or use a venv).
2. `export DISCORD_WEBHOOK_URL="..."` (or hardcode it in a wrapper shell
   script that launchd calls -- don't commit secrets to any file).
3. A `launchd` plist that runs `python3 /path/to/bot.py` every 20
   minutes, e.g.:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourname.audiodealfinder</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/you/audio_deal_finder/bot.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/you/audio_deal_finder</string>
    <key>StartInterval</key>
    <integer>1200</integer>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DISCORD_WEBHOOK_URL</key>
        <string>your_webhook_url_here</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/audiodealfinder.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/audiodealfinder.err</string>
</dict>
</plist>
```

Save as `~/Library/LaunchAgents/com.yourname.audiodealfinder.plist`, then
`launchctl load ~/Library/LaunchAgents/com.yourname.audiodealfinder.plist`.
This gets you real-time scheduling (no GitHub cron jitter) and removes
the CI/cache complexity entirely -- `seen_listings.json` just lives on
your disk.

## Known remaining trade-offs

- Still no headless browser / proxy pool, by design -- some marketplaces
  behind aggressive WAFs (eBay, some Craigslist regions under heavy
  load) may still intermittently block plain `requests`. If that
  becomes a real problem, the next honest step up is `curl_cffi` for
  TLS fingerprint spoofing, which is still free but adds a dependency.
- Craigslist fetch volume scales as `regions × keywords`; keep
  `CRAIGSLIST_REGIONS` and the watchlist reasonably sized, or you risk
  soft rate-limiting despite the delay.
- Reddit's public JSON endpoint is unauthenticated and could change
  rate limits or require OAuth in the future without notice.
