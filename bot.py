import json
import os
import requests

# --- CONFIGURATION ---
SEEN_FILE = "seen_listings.json"
MAX_SEEN_ITEMS = 1000  # Caps the file size so it never grows infinitely
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# --- DEDUPLICATION STORAGE ---
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
    """Saves updated set of listing IDs to disk with a rolling memory window."""
    # Keep only the last MAX_SEEN_ITEMS to prevent bloating
    seen_list = list(seen_ids)[-MAX_SEEN_ITEMS:]
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(seen_list, f, indent=2)
    except Exception as e:
        print(f"Error saving {SEEN_FILE}: {e}")

# --- DISCORD NOTIFICATIONS ---
def send_discord_alert(item):
    """Sends a formatted alert embed to your Discord channel."""
    payload = {
        "embeds": [{
            "title": f"🚨 Deal Found: {item['title']}",
            "url": item["url"],
            "color": 3066993,  # Green
            "fields": [
                {"name": "Price", "value": f"${item['price']}", "inline": True},
                {"name": "Platform", "value": item.get("platform", "Marketplace"), "inline": True},
            ]
        }]
    }
    
    if DISCORD_WEBHOOK_URL:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code != 204:
            print(f"Discord Webhook Error: {response.status_code}")
    else:
        print(f"[TEST MODE] New Deal: {item['title']} - ${item['price']}")

# --- MAIN DEDUPLICATION PROCESSOR ---
def process_scraped_items(scraped_items):
    """
    Checks scraped listings against seen history.
    Only notifies on brand new matches and updates storage.
    """
    seen_ids = load_seen_ids()
    new_alerts_count = 0

    for item in scraped_items:
        # Use a unique listing ID, or fallback to the direct URL
        item_id = item.get("id") or item.get("url")
        
        if not item_id:
            continue

        # 1. Skip immediately if we've already notified on this item
        if item_id in seen_ids:
            continue

        # 2. If it's a new match, record it and send alert
        seen_ids.add(item_id)
        send_discord_alert(item)
        new_alerts_count += 1

    # Save updated history back to disk
    save_seen_ids(seen_ids)
    print(f"Processed batch. Sent {new_alerts_count} new alert(s).")

# Example Entry Point
if __name__ == "__main__":
    # Your scraper functions feed clean listing dicts here:
    scraped_data = [
        # Example format:
        # {"id": "craigslist_771234", "title": "KEF LS50 Meta - Mint", "price": 750, "url": "https://...", "platform": "Craigslist"}
    ]
    process_scraped_items(scraped_data)
