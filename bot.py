import os
import re
import bs4
import feedparser
import requests

# ==============================================================================
# 1. WATCHLIST CONFIGURATION
# ==============================================================================
WATCHLIST = [
    # --------------------------------------------------------------------------
    # DESKTOP ISOLATION
    # --------------------------------------------------------------------------
    {
        "name": "IsoAcoustics Aperta",
        "max_price": 110.00,
        "query": "isoacoustics aperta",
    },
    # --------------------------------------------------------------------------
    # SPEAKERS
    # --------------------------------------------------------------------------
    {
        "name": "KEF LS50 / LS50 Meta",
        "max_price": 1650.00,  # Set to $1,650 to test alert triggers
        "query": "ls50",  # Broad search term catches LS50, LS50 Meta, LS50W
    },
    {
        "name": "Revel Performa3 M106 (UNICORN)",
        "max_price": 850.00,
        "query": "revel m106",
    },
    {
        "name": "KEF R3 Meta (UNICORN)",
        "max_price": 1100.00,
        "query": "r3 meta",
    },
    {
        "name": "Ascend Sierra LX (UNICORN)",
        "max_price": 850.00,
        "query": "sierra lx",
    },
    {
        "name": "Buchardt S400 MKII (UNICORN)",
        "max_price": 950.00,
        "query": "s400",
    },
    # --------------------------------------------------------------------------
    # SUBWOOFERS
    # --------------------------------------------------------------------------
    {
        "name": "SVS SB-2000 Pro / SB-3000 (UNICORN)",
        "max_price": 450.00,
        "query": "svs sb",
    },
    {
        "name": "REL T/7x or T/9x (UNICORN)",
        "max_price": 500.00,
        "query": "rel t",
    },
    {
        "name": "SVS 3000 Micro (UNICORN)",
        "max_price": 450.00,
        "query": "3000 micro",
    },
]

# Set your local Craigslist region subdomain
CRAIGSLIST_REGION = "losangeles"

# Discord Webhook pulled securely from GitHub Secrets
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# Headers configured for browser emulation and Reverb API compatibility
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Version": "3.0",  # Required for Reverb API v3
}


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
def extract_price(text):
    """Extracts a numerical float price from text strings."""
    if not text:
        return None

    # Primary regex: Match prices preceded by $ (e.g., $1,650.00 or $1650)
    match = re.search(r"\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Fallback regex: Look for standalone numbers in standard price ranges
    match_raw = re.search(r"\b(\d{3,4}(?:\.\d{2})?)\b", text)
    if match_raw:
        try:
            val = float(match_raw.group(1))
            if 50 <= val <= 10000:
                return val
        except ValueError:
            pass

    return None


def send_discord_alert(title, price, url, source, target_name):
    """Sends a formatted Embed notification card to your Discord server."""
    if not DISCORD_WEBHOOK:
        print("[WARNING] DISCORD_WEBHOOK environment variable not found.")
        return

    price_str = f"${price:.2f}" if price else "Check Listing"

    embed = {
        "title": f"🚨 Deal Alert: {target_name} ({price_str})",
        "description": f"**Title:** {title}\n**Source:** {source}\n[View Listing]({url})",
        "url": url,
        "color": 3066993,  # Green accent color
        "fields": [
            {"name": "Price", "value": price_str, "inline": True},
            {"name": "Source", "value": source, "inline": True},
        ],
        "footer": {"text": "Audio Deal Finder • GitHub Actions"},
    }

    payload = {"embeds": [embed]}

    try:
        response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        response.raise_for_status()
        print(f"[ALERT SENT] {title} ({price_str}) on {source}")
    except Exception as e:
        print(f"[ERROR] Failed to send Discord alert: {e}")


# ==============================================================================
# 3. SCRAPING & API MODULES
# ==============================================================================
def check_craigslist(item):
    """Checks Craigslist RSS feed for matching queries and price limits."""
    query = item["query"].replace(" ", "+")
    max_price = item["max_price"]
    rss_url = f"https://{CRAIGSLIST_REGION}.craigslist.org/search/sss?format=rss&query={query}"

    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            title = entry.title
            link = entry.link
            price = extract_price(title) or extract_price(
                entry.get("summary", "")
            )

            if price and price <= max_price:
                send_discord_alert(
                    title, price, link, "Craigslist", item["name"]
                )
    except Exception as e:
        print(f"[ERROR] Craigslist parsing failed for {item['name']}: {e}")


def check_us_audio_mart(item):
    """Checks US Audio Mart for matching queries and price limits."""
    query = item["query"].replace(" ", "+")
    max_price = item["max_price"]
    search_url = f"https://www.usaudiomart.com/search.php?keywords={query}"

    try:
        res = requests.get(search_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return

        soup = bs4.BeautifulSoup(res.text, "html.parser")
        results = soup.select(".search_result") or soup.select(
            ".list-group-item"
        )

        for result in results[:5]:
            title_tag = result.select_one("a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = title_tag.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://www.usaudiomart.com{link}"

            price_tag = result.select_one(".price") or result
            price = extract_price(price_tag.get_text()) if price_tag else None

            if price and price <= max_price:
                send_discord_alert(
                    title, price, link, "US Audio Mart", item["name"]
                )
    except Exception as e:
        print(f"[ERROR] US Audio Mart parsing failed for {item['name']}: {e}")


def check_reverb(item):
    """Checks Reverb's public API endpoint for matching listings."""
    query = item["query"].replace(" ", "%20")
    max_price = item["max_price"]
    api_url = f"https://api.reverb.com/api/listings?query={query}&price_max={max_price}&currency=USD"

    try:
        res = requests.get(api_url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for listing in data.get("listings", [])[:5]:
                title = listing.get("title")
                price = float(listing.get("price", {}).get("amount", 0))
                link = listing.get("_links", {}).get("web", {}).get("href")

                if price and price <= max_price:
                    send_discord_alert(
                        title, price, link, "Reverb", item["name"]
                    )
    except Exception as e:
        print(f"[ERROR] Reverb parsing failed for {item['name']}: {e}")


def check_ebay(item):
    """Checks eBay RSS feed for matching queries and price limits."""
    query = item["query"].replace(" ", "+")
    max_price = item["max_price"]
    rss_url = f"https://www.ebay.com/sch/i.html?_nkw={query}&_udhi={max_price}&_rss=1"

    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            title = entry.title
            link = entry.link
            price = extract_price(title) or extract_price(
                entry.get("summary", "")
            )

            if price and price <= max_price:
                send_discord_alert(title, price, link, "eBay", item["name"])
    except Exception as e:
        print(f"[ERROR] eBay parsing failed for {item['name']}: {e}")


def check_asr_classifieds(item):
    """Checks Audio Science Review (ASR) Buy/Sell forum RSS feed."""
    rss_url = "https://www.audiosciencereview.com/forum/index.php?forums/audio-equipment-for-sale-or-to-buy.29/index.rss"
    query_terms = item["query"].lower().split()
    max_price = item["max_price"]

    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:10]:
            title = entry.title
            title_lower = title.lower()

            if all(term in title_lower for term in query_terms):
                link = entry.link
                price = extract_price(title) or extract_price(
                    entry.get("summary", "")
                )

                if price and price <= max_price:
                    send_discord_alert(
                        title, price, link, "ASR Forum", item["name"]
                    )
    except Exception as e:
        print(f"[ERROR] ASR Forum parsing failed for {item['name']}: {e}")


# ==============================================================================
# 4. MAIN EXECUTION
# ==============================================================================
def main():
    print("Starting master deal scan across all audio marketplaces...")
    for item in WATCHLIST:
        print(f"Scanning for: {item['name']} (Max Price: ${item['max_price']})")
        check_craigslist(item)
        check_us_audio_mart(item)
        check_reverb(item)
        check_ebay(item)
        check_asr_classifieds(item)
    print("Scan complete!")


if __name__ == "__main__":
    main()
