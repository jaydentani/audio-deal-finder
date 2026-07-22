import os
import re
import feedparser
import requests
import base64

# ==============================================================================
# 1. WATCHLIST CONFIGURATION
# ==============================================================================
WATCHLIST = [
    {"name": "IsoAcoustics Aperta", "max_price": 110.00, "query": "isoacoustics"},
    {"name": "KEF LS50 / LS50 Meta", "max_price": 1650.00, "query": "kef ls50"},
    {"name": "Revel Performa3 M106", "max_price": 850.00, "query": "revel"},
    {"name": "KEF R3 Meta", "max_price": 1100.00, "query": "kef r3"},
    {"name": "Ascend Sierra LX", "max_price": 850.00, "query": "ascend"},
    {"name": "Buchardt S400 MKII", "max_price": 950.00, "query": "buchardt"},
    {"name": "SVS SB-2000 Pro / SB-3000", "max_price": 450.00, "query": "svs sb"},
    {"name": "REL T/7x or T/9x", "max_price": 500.00, "query": "rel t"},
    {"name": "SVS 3000 Micro", "max_price": 450.00, "query": "svs 3000"},
]

CRAIGSLIST_REGION = "losangeles"

# Credentials pulled securely from GitHub Secrets
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EBAY_APP_ID = os.getenv("EBAY_APP_ID")
EBAY_CERT_ID = os.getenv("EBAY_CERT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Version": "3.0",
}

# ==============================================================================
# 2. HELPER & LLM FUNCTIONS
# ==============================================================================
def extract_price(text):
    if not text: return None
    
    match = re.search(r"\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", text)
    if match:
        try: return float(match.group(1).replace(",", ""))
        except ValueError: pass
        
    match_raw = re.search(r"\b(\d{3,4}(?:\.\d{2})?)\b", text)
    if match_raw:
        try:
            val = float(match_raw.group(1))
            if 50 <= val <= 10000: return val
        except ValueError: pass
    return None

def evaluate_deal_with_llm(target_item, listing_title, listing_price):
    if not GEMINI_API_KEY:
        print("[WARNING] No Gemini API key. Dropping listing.")
        return False 
        
    prompt = f"""
    Task: Binary Classification of Audio Equipment Listings.
    Target Item Wanted: '{target_item}'
    Listing Title: '{listing_title}'
    Listing Price: ${listing_price}
    
    Evaluate if the Listing Title EXACTLY matches the Target Item Wanted.
    Reject parts, single speakers (if pair expected), and empty boxes.
    Output exactly one word: YES or NO.
    """
    
# Updated to use the active 3.5-flash model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={GEMINI_API_KEY}"    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 5}
    }
    
    try:
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        res.raise_for_status()
        text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
        return "YES" in text
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return False

def send_discord_alert(title, price, url, source, target_name):
    if not DISCORD_WEBHOOK: return
    price_str = f"${price:.2f}" if price else "Check Listing"
    embed = {
        "title": f"🚨 Deal Alert: {target_name} ({price_str})",
        "description": f"**Title:** {title}\n**Source:** {source}\n[View Listing]({url})",
        "url": url,
        "color": 3066993,
    }
    try:
        requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        print(f"[ALERT SENT] {title} ({price_str}) on {source}")
    except Exception as e:
        print(f"[ERROR] Discord: {e}")

def send_status_warning(failed_services):
    """Sends a notification if one or more search platforms were unreachable."""
    if not DISCORD_WEBHOOK or not failed_services:
        return

    services_str = ", ".join(set(failed_services))
    embed = {
        "title": "⚠️ Deal Finder: Service Status Notice",
        "description": f"The following search modules encountered errors or were unreachable during this run:\n**{services_str}**\n\nAll other searches completed successfully.",
        "color": 16753920,  # Orange warning color
        "footer": {"text": "Audio Deal Finder • Health Check"},
    }

    try:
        requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to send status warning: {e}")

# ==============================================================================
# 3. NATIVE APIs & RSS SCRAPING
# ==============================================================================
def check_craigslist(item):
    query = item["query"].replace(" ", "+")
    rss_url = f"https://{CRAIGSLIST_REGION}.craigslist.org/search/sss?format=rss&query={query}"
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            price = extract_price(entry.title) or extract_price(entry.get("summary", ""))
            if price and price <= item["max_price"]:
                if evaluate_deal_with_llm(item["name"], entry.title, price):
                    send_discord_alert(entry.title, price, entry.link, "Craigslist", item["name"])
    except Exception as e:
        print(f"[ERROR] Craigslist: {e}")

def check_asr_classifieds(item):
    rss_url = "https://www.audiosciencereview.com/forum/index.php?forums/audio-equipment-for-sale-or-to-buy.29/index.rss"
    query_terms = item["query"].lower().split()
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:10]:
            title_lower = entry.title.lower()
            if all(term in title_lower for term in query_terms):
                price = extract_price(entry.title) or extract_price(entry.get("summary", ""))
                if price and price <= item["max_price"]:
                    if evaluate_deal_with_llm(item["name"], entry.title, price):
                        send_discord_alert(entry.title, price, entry.link, "ASR Forum", item["name"])
    except Exception as e:
        print(f"[ERROR] ASR Forum: {e}")

def check_reverb(item):
    query = item["query"].replace(" ", "%20")
    api_url = f"https://api.reverb.com/api/listings?query={query}&price_max={item['max_price']}&currency=USD"
    try:
        res = requests.get(api_url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for listing in res.json().get("listings", [])[:5]:
                title = listing.get("title")
                price = float(listing.get("price", {}).get("amount", 0))
                link = listing.get("_links", {}).get("web", {}).get("href")
                if price and price <= item["max_price"]:
                    if evaluate_deal_with_llm(item["name"], title, price):
                        send_discord_alert(title, price, link, "Reverb", item["name"])
    except Exception as e:
        print(f"[ERROR] Reverb: {e}")

def get_ebay_token():
    if not EBAY_APP_ID or not EBAY_CERT_ID: return None
    url = "https://api.ebay.com/identity/v1/oauth2/token"
    auth_str = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Basic {auth_str}"}
    data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
    try:
        res = requests.post(url, headers=headers, data=data, timeout=10)
        return res.json().get("access_token")
    except Exception as e:
        print(f"[ERROR] eBay Auth: {e}")
        return None

def check_ebay_api(item, token):
    if not token: return
    query = item["query"].replace(" ", "%20")
    url = f"https://api.ebay.com/buy/browse/v1/item_summary/search?q={query}&filter=price:[..{item['max_price']}],priceCurrency:USD"
    headers = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            for summary in res.json().get("itemSummaries", [])[:5]:
                title = summary.get("title")
                price = float(summary.get("price", {}).get("value", 0))
                link = summary.get("itemWebUrl")
                if price and price <= item["max_price"]:
                    if evaluate_deal_with_llm(item["name"], title, price):
                        send_discord_alert(title, price, link, "eBay", item["name"])
    except Exception as e:
        print(f"[ERROR] eBay Search: {e}")

# ==============================================================================
# 4. MAIN EXECUTION
# ==============================================================================
def main():
    print("Starting Clean API & RSS Deal Scan...")
    failed_services = set()

    # Safely attempt eBay authentication
    ebay_token = None
    try:
        ebay_token = get_ebay_token()
        if not ebay_token and (EBAY_APP_ID and EBAY_CERT_ID):
            failed_services.add("eBay (Auth Pending/Failed)")
    except Exception as e:
        print(f"[ERROR] eBay token fetch failed: {e}")
        failed_services.add("eBay API")

    # Run searches with individual fallback wrappers
    for item in WATCHLIST:
        print(f"Scanning for: {item['name']}...")

        # Craigslist
        try:
            check_craigslist(item)
        except Exception as e:
            print(f"[ERROR] Craigslist module failed: {e}")
            failed_services.add("Craigslist")

        # ASR Forum
        try:
            check_asr_classifieds(item)
        except Exception as e:
            print(f"[ERROR] ASR Forum module failed: {e}")
            failed_services.add("ASR Forum")

        # Reverb
        try:
            check_reverb(item)
        except Exception as e:
            print(f"[ERROR] Reverb module failed: {e}")
            failed_services.add("Reverb")

        # eBay
        if ebay_token:
            try:
                check_ebay_api(item, ebay_token)
            except Exception as e:
                print(f"[ERROR] eBay search failed: {e}")
                failed_services.add("eBay Search")

    # If any services failed during the run, send a single summary warning to Discord
    if failed_services:
        print(
            f"[STATUS NOTICE] The following services failed: {failed_services}"
        )
        # Uncomment the line below if you want Discord pings when a site drops:
        # send_status_warning(failed_services)

    print("Scan complete!")


if __name__ == "__main__":
    main()
