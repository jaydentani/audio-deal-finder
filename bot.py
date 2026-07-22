import json
import os
import re
import requests
import xml.etree.ElementTree as ET

# ==========================================
# CONFIGURATION
# ==========================================
SEEN_FILE = "seen_listings.json"
MAX_SEEN_ITEMS = 1000  # Keeps file lightweight by capping memory history
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Define your target watchlist and maximum price caps
TARGET_WATCHLIST = [
    {"keyword": "kef ls50", "max_price": 850},
    {"keyword": "kef r3", "max_price": 1100},
    {"keyword": "isoacoustics", "max_price": 100},
    {"keyword": "iso-155", "max_price": 90},
    {"keyword": "aperta", "max_price": 120},
    {"keyword": "sierra", "max_price": 800},
]

# ==========================================
# STORAGE & DEDUPLICATION
# ==========================================
def load_seen_ids():
    """Loads previously notified listing IDs or URLs from local JSON storage."""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Warning: Could not read {SEEN_FILE} ({e}). Starting fresh.")
            return set()
    return set()

def save_seen_ids(seen_ids):
    """Saves updated set of listing IDs back to disk with a rolling memory window."""
    seen_list = list(seen_ids)[-MAX_SEEN_ITEMS:]
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(seen_list, f, indent=2)
    except Exception as e:
        print(f"Error saving {SEEN_FILE}: {e}")

# ==========================================
# HELPER PARSERS & MATCHERS
# ==========================================
def extract_price(text):
    """Extracts dollar values (e.g., '$750' or '$1,200') from listing titles."""
    match = re.search(r'\$\s*([0-9,]+)', text)
    if match:
        try:
            return float(match.group(1).replace(',', ''))
        except ValueError:
            return None
    return None

def is_target_match(item):
    """Evaluates if a listing matches title keywords and respects price caps."""
    title_lower = item["title"].lower()
    item_price = item.get("price")

    for target in TARGET_WATCHLIST:
        if target["keyword"] in title_lower:
            # If no price limit specified or price is within budget, trigger match
            if target["max_price"] is None or item_price is None or item_price <= target["max_price"]:
                return True
    return False

# ==========================================
# DISCORD NOTIFICATIONS
# ==========================================
def send_discord_alert(item):
    """Sends a rich embed notification to your Discord channel."""
    price_str = f"${item['price']:,.2f}" if item.get('price') else "Check Listing"
    
    payload = {
        "embeds": [{
            "title": f"🚨 Deal Match: {item['title']}",
            "url": item["url"],
            "color": 3066993,  # Emerald Green
            "fields": [
                {"name": "Price", "value": price_str, "inline": True},
                {"name": "Platform", "value": item.get("platform", "Audio Marketplace"), "inline": True},
            ],
            "footer": {"text": "Audio Deal Finder • Live Alert"}
        }]
    }

    if DISCORD_WEBHOOK_URL:
        try:
            res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            if res.status_code == 204:
                print(f"✅ Sent Discord alert for: {item['title']}")
            else:
                print(f"⚠️ Discord Webhook returned status code {res.status_code}")
        except Exception as e:
            print(f"❌ Failed to send Discord alert: {e}")
    else:
        print(f"[TEST MODE - No Webhook Set] Match: {item['title']} | Price: {price_str} | URL: {item['url']}")

# ==========================================
# SCRAPER FEED PIPELINE
# ==========================================
def fetch_listings():
    """
    Fetches listings from configured feeds.
    Returns a list of clean dicts: {'id', 'title', 'price', 'url', 'platform'}
    """
    listings = []

    # Add RSS feed endpoints here (e.g., US Audio Mart RSS)
    rss_sources = [
        {"url": "https://www.usaudiomart.com/rss.php", "platform": "US Audio Mart"},
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for source in rss_sources:
        try:
            resp = requests.get(source["url"], headers=headers, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for entry in root.findall(".//item"):
                    title = entry.find("title").text if entry.find("title") is not None else ""
                    link = entry.find("link").text if entry.find("link") is not None else ""
                    
                    price = extract_price(title)
                    
                    if title and link:
                        listings.append({
                            "id": link,  # Uses the unique item URL as the primary identifier
                            "title": title,
                            "price": price,
                            "url": link,
                            "platform": source["platform"]
                        })
        except Exception as e:
            print(f"Error fetching {source['platform']}: {e}")

    return listings

# ==========================================
# MAIN ROUTINE
# ==========================================
def main():
    print("🔍 Starting deal scan...")
    
    seen_ids = load_seen_ids()
    scraped_items = fetch_listings()
    new_alerts = 0

    for item in scraped_items:
        item_id = item.get("id") or item.get("url")
        if not item_id:
            continue

        # 1. Skip if already processed in a previous run
        if item_id in seen_ids:
            continue

        # Mark as seen immediately
        seen_ids.add(item_id)

        # 2. Check if listing matches target watchlist criteria
        if is_target_match(item):
            send_discord_alert(item)
            new_alerts += 1

    # Save updated state to persistent storage
    save_seen_ids(seen_ids)
    print(f"Scan complete. Inspected {len(scraped_items)} item(s). Sent {new_alerts} new alert(s).")

if __name__ == "__main__":
    main()
