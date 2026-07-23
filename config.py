"""
Central configuration for the Audio Deal Finder Bot.

Edit TARGET_WATCHLIST to add/remove gear you're hunting for.
Edit GLOBAL_NEGATIVE_KEYWORDS to tune out false positives across all targets.
"""

# ==========================================
# GLOBAL NEGATIVE KEYWORDS
# ==========================================
# Any listing whose title contains one of these (case-insensitive) is
# rejected before it's even checked against the watchlist.
GLOBAL_NEGATIVE_KEYWORDS = [
    "wanted",
    "wtb",
    "want to buy",
    "looking for",
    "iso ",          # "ISO <item>" = "in search of", common on Reddit/CL
    "box only",
    "boxes only",
    "box/manual only",
    "empty box",
    "broken",
    "cracked",
    "damaged",
    "for parts",
    "parts only",
    "not working",
    "does not work",
    "repair",
]

# ==========================================
# TARGET WATCHLIST
# ==========================================
# keyword            : substring to match in the title (case-insensitive)
# max_price           : reject matches priced above this (None = no cap)
# negative_keywords    : extra per-target exclusions (merged with global list)
TARGET_WATCHLIST = [
    {"keyword": "kef ls50", "max_price": 850, "negative_keywords": []},
    {"keyword": "kef r3", "max_price": 1100, "negative_keywords": []},
    {"keyword": "isoacoustics", "max_price": 100, "negative_keywords": []},
    {"keyword": "iso-155", "max_price": 90, "negative_keywords": []},
    {"keyword": "aperta", "max_price": 120, "negative_keywords": []},
    {"keyword": "sierra", "max_price": 800, "negative_keywords": ["fiat", "jeep", "car", "truck"]},
]

# ==========================================
# FEED SOURCES
# ==========================================
USAUDIOMART_RSS_URL = "https://www.usaudiomart.com/rss.php?class_id=0"

REDDIT_SUBREDDITS = ["AVexchange"]
# Reddit requires a descriptive User-Agent or it will 429 you almost immediately.
REDDIT_USER_AGENT = "android:com.audiodealfinder.app:v1.0 (by u/Unhappy-Plate-1916)"

# Craigslist search RSS: {region}.craigslist.org/search/{category}?query={kw}&format=rss
# "ela" = "electronics - by owner". Add/remove regions you're willing to drive to.
CRAIGSLIST_REGIONS = [
    "sfbay",
    "losangeles",
    "sandiego",
    "seattle",
]
CRAIGSLIST_CATEGORY = "ela"
CRAIGSLIST_REQUEST_DELAY_SECONDS = 3  # be polite; avoid tripping rate limits

# ==========================================
# STORAGE
# ==========================================
SEEN_FILE = "seen_listings.json"
MAX_SEEN_ITEMS = 2000

DISCORD_WEBHOOK_URL_ENV = "DISCORD_WEBHOOK_URL"

# ==========================================
# REVERB (official API -- personal access token, free)
# Get yours at: reverb.com -> Settings -> Advanced -> API Tokens
# ==========================================
REVERB_ACCESS_TOKEN_ENV = "REVERB_ACCESS_TOKEN"

# ==========================================
# EBAY (official Browse API -- free developer account, OAuth client
# credentials flow, no user login needed)
# Get keys at: developer.ebay.com -> your Production Keyset
# ==========================================
EBAY_CLIENT_ID_ENV = "EBAY_CLIENT_ID"
EBAY_CLIENT_SECRET_ENV = "EBAY_CLIENT_SECRET"
EBAY_MARKETPLACE_ID = "EBAY_US"

# ==========================================
# HEADLESS BROWSER FALLBACK (Playwright)
# Used only when a plain requests.get() hits a Cloudflare JS challenge
# (see feeds/browser_fetch.py). Requires:
#   pip install playwright && playwright install --with-deps chromium
# ==========================================
BROWSER_CHALLENGE_WAIT_MS = 6000
