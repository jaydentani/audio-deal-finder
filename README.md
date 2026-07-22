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
│   ├── base.py                  # shared HTTP helpers (safe_get, get_raw)
│   ├── browser_fetch.py           # Playwright Cloudflare-challenge fallback
│   ├── usaudiomart.py
│   ├── reddit_avexchange.py
│   ├── craigslist.py
│   ├── reverb.py
│   └── ebay.py
├── requirements.txt
├── requirements-browser.txt   # optional: Playwright, for the CF fallback
└── .github/workflows/main.yml
```
Logging replaces `print()` throughout (`logging.basicConfig` in
`bot.py`), each feed module fails independently (one bad source can't
crash the whole scan), and everything is PEP-8 formatted.

## Migrating to a Mac (`launchd`)

Nothing in `bot.py`/`storage.py` needs to change. Steps:

1. **Set up a virtual environment and install dependencies:**
   ```bash
   cd ~/audio_deal_finder
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-browser.txt
   playwright install chromium
   ```
   Note: on macOS, install Chromium with just `playwright install chromium`
   -- **not** `--with-deps`. That flag installs Linux apt packages for CI
   runners and doesn't apply here.

2. **Test it manually before scheduling anything:**
   ```bash
   python3 bot.py
   ```
   Check the log output to confirm which feeds return listings vs. skip.

3. **Set your credentials in the `launchd` plist**, not your shell
   profile -- `launchd` doesn't inherit your Terminal's environment, so
   `export`-ing a variable in `.zshrc` won't reach it. Use the
   `EnvironmentVariables` block below. You need all three you set up as
   GitHub secrets: `DISCORD_WEBHOOK_URL`, `REVERB_ACCESS_TOKEN`,
   `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`.

4. **Create the plist**, pointing `ProgramArguments` at your **venv's**
   Python (not system Python, or it won't see the installed packages):

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
        <string>/Users/you/audio_deal_finder/venv/bin/python3</string>
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
        <key>REVERB_ACCESS_TOKEN</key>
        <string>your_reverb_token_here</string>
        <key>EBAY_CLIENT_ID</key>
        <string>your_ebay_client_id_here</string>
        <key>EBAY_CLIENT_SECRET</key>
        <string>your_ebay_client_secret_here</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/audiodealfinder.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/audiodealfinder.err</string>
</dict>
</plist>
```

5. **Load it:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.yourname.audiodealfinder.plist
   ```
   This gets you real-time scheduling (no GitHub cron jitter) and removes
   the CI/cache complexity entirely -- `seen_listings.json` just lives on
   your disk.

6. **Disable the GitHub Actions workflow once the Mac version is
   confirmed working.** This step matters: if both run at the same time,
   you'll get duplicate Discord alerts, because your Mac's
   `seen_listings.json` and the one in the GitHub Actions cache are two
   separate, unsynced dedup histories -- each will think a listing is
   "new" the first time *it* sees it. Easiest fix without deleting
   anything: open `.github/workflows/main.yml` and remove (or comment
   out) the `schedule:` block, leaving `workflow_dispatch:` so you can
   still trigger it manually later if you ever want to:
   ```yaml
   on:
     # schedule:
     #   - cron: '*/20 * * * *'
     workflow_dispatch:
   ```

## New sources added

### Reverb & eBay (`feeds/reverb.py`, `feeds/ebay.py`)
Both use official free APIs -- no scraping, no ToS risk, and price comes
straight from structured JSON instead of regex-guessing it from a title.

- **Reverb**: get a personal access token at reverb.com -> Settings ->
  Advanced -> API Tokens. Set it as `REVERB_ACCESS_TOKEN`.
- **eBay**: create a free developer account at developer.ebay.com, grab
  your app's *Production* Client ID/Secret. Set `EBAY_CLIENT_ID` and
  `EBAY_CLIENT_SECRET`. The bot handles the OAuth client-credentials
  token exchange and caches it in-process (tokens last ~2hrs).

Both feeds skip themselves cleanly (log a warning, return no listings)
if their env vars aren't set -- they won't crash the run.

**On GitHub Actions**: add these as repo secrets (Settings -> Secrets
and variables -> Actions) alongside `DISCORD_WEBHOOK_URL`. The workflow
already wires them through.

**Locally / on your Mac**: add them to your `launchd` plist's
`EnvironmentVariables` block, same as the Discord webhook.

### Cloudflare challenge fallback (`feeds/browser_fetch.py`)
US Audio Mart and Craigslist confirmed (via the `cf-mitigated: challenge`
response header) that they issue a Cloudflare JS challenge to *any*
plain HTTP client -- this reproduced identically from a residential Mac
IP and from GitHub Actions, so it's not IP-reputation blocking, it's a
JS-execution requirement.

Both feeds now try a fast `requests.get()` first, and only fall back to
a headless Chromium (Playwright) when that request comes back with the
challenge marker. This keeps normal runs fast and only pays the
browser-launch cost (a few seconds) on sources that are actually
blocking you.

**Setup**: `pip install -r requirements-browser.txt` then install the
Chromium binary -- `playwright install --with-deps chromium` on Linux/CI
(the `--with-deps` flag pulls in required apt packages), or just
`playwright install chromium` on macOS. The GitHub Actions workflow does
this automatically, with the Chromium binary cached so it's only slow on
the first run.

**Be aware this isn't a guaranteed fix**: it handles Cloudflare's
*managed* challenge (auto-resolves once JS runs), but not an
*interactive* Turnstile challenge (needs a click/puzzle) -- that would
require a human or a paid solving service, both intentionally out of
scope here. If you start seeing `"still looks like a challenge page"`
warnings consistently, that's the signal you've hit that ceiling.

### Facebook Marketplace & OfferUp -- not automated, on purpose
Neither has a public API. Both require a logged-in session, run heavy
anti-bot JS, and Facebook's ToS explicitly prohibits automated scraping
of Marketplace -- the realistic risk isn't just "the scraper breaks,"
it's your account getting flagged. I didn't build scrapers for these.
If you want a lightweight, zero-risk version of this later, a small
script that just generates saved-search URLs for you to check manually
(or a reminder ping) is a reasonable middle ground -- say the word if
you want that added.

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
