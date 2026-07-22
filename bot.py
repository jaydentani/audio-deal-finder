import os
import re
import bs4
import feedparser
import requests

# ==============================================================================
# 1. WATCHLIST CONFIGURATION
# ==============================================================================
WATCHLIST = [
    {"name": "IsoAcoustics Aperta", "max_price": 110.00, "query": "isoacoustics aperta"},
    {"name": "KEF LS50 / LS50 Meta", "max_price": 1650.00, "query": "ls50"},
    {"name": "Revel Performa3 M106", "max_price": 850.00, "query": "revel m106"},
    {"name": "KEF R3 Meta", "max_price": 1100.00, "query": "r3 meta"},
    {"name": "Ascend Sierra LX", "max_price": 850.00, "query": "sierra lx"},
    {"name": "Buchardt S400 MKII", "max_price": 950.00, "query": "s400"},
    {"name": "SVS SB-2000 Pro / SB-3000", "max_price": 450.00, "query": "svs sb"},
    {"name": "REL T/7x or T/9x", "max_price": 500.00, "query": "rel t"},
    {"name": "SVS 3000 Micro", "max_price": 450.00, "query": "3000 micro"},
]

CRAIGSLIST_REGION = "losangeles"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Version": "3.0",
}


# ==============================================================================
# 2. HELPER & LLM FUNCTIONS
# ==============================================================================
def extract_price(text):
    if not text:
        return None
    match = re.search(r"\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    match_raw = re.search(r"\b(\d{3,4}(?:\.\d{2})?)\b", text)
    if match_raw:
        try:
            val = float(match_raw.group(1))
            if 50 <= val <= 10000:
                return val
        except ValueError:
            pass
    return None

def evaluate_deal_with_llm(target_item, listing_title, listing_price):
    """Uses Google's Gemini API as a zero-shot classifier to filter out fuzzy match garbage."""
    if not GEMINI_API_KEY:
        return True  # Fallback to allowing the ping if no key is configured
        
    prompt = f"""
    You are an audiophile and expert gear reviewer filtering a classifieds feed.
    I am specifically looking to buy this exact item family: '{target_item}'.
    
    A seller just posted this listing:
    Title: '{listing_title}'
    Price: ${listing_price}
    
    Is this listing EXACTLY the item I am looking for? 
    Rules:
    - If I want 'IsoAcoustics Aperta', an 'ISO-Puck' or 'Orea' is NO.
    - If I want 'REL T/7x', a 'REL T/5x' or 'Tzero' is NO.
    - If it is just a part, empty box, or a tiny accessory, say NO.
    
    Answer with ONLY a single word: YES or NO.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
        if "YES" in text:
            return True
        return False
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return True

def send_discord_alert(title, price, url, source, target_name):
    if not DISCORD_WEBHOOK:
        return
    price_str = f"${price:.2f}" if price else "Check Listing"
    embed = {
        "title": f"🚨 Deal Alert: {target_name} ({price_str})",
        "description": f"**Title:** {title}\n**Source:** {source}\n[View Listing]({url})",
        "url": url,
        "color": 3066993,
        "fields": [
            {"name": "Price", "value": price_str, "inline": True},
            {"name": "Source", "value": source, "inline": True},
        ],
        "footer": {"text": "Audio Deal Finder • AI Filtered"},
    }
    try:
        requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        print(f"[ALERT SENT] {title} ({price_str}) on {source}")
    except Exception as e:
        print(f"[ERROR] Discord alert failed: {e}")


# ==============================================================================
# 3. SCRAPING & API MODULES
# ==============================================================================
def check_craigslist(item):
    query = item["query"].replace(" ", "+")
    rss_url = f"https://{CRAIGSLIST_REGION}.craigslist.org/search/sss?format=rss&query={query}"
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            title = entry.title
            link = entry.link
            price = extract_price(title) or extract_price(entry.get("summary", ""))
            if price and price <= item["max_price"]:
                if evaluate_deal_with_llm(item["name"], title, price):
                    send_discord_alert(title, price, link, "Craigslist", item["name"])
    except Exception as e:
        print(f"[ERROR] Craigslist: {e}")

def check_us_audio_mart(item):
    query = item["query"].replace(" ", "+")
    search_url = f"https://www.usaudiomart.com/search.php?keywords={query}"
    try:
        res = requests.get(search_url, headers=HEADERS, timeout=10)
        soup = bs4.BeautifulSoup(res.text, "html.parser")
        # Broadened CSS selectors to catch USAM layout shifts
        results = soup.select(".search_result, .list-group-item, .listing-item, div.item")
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
            
            if price and price <= item["max_price"]:
                if evaluate_deal_with_llm(item["name"], title, price):
                    send_discord_alert(title, price, link, "US Audio Mart", item["name"])
    except Exception as e:
        print(f"[ERROR] US Audio Mart: {e}")

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

def check_ebay(item):
    """eBay deprecated RSS, using direct HTML parsing instead."""
    query = item["query"].replace(" ", "+")
    url = f"https://www.ebay.com/sch/i.html?_nkw={query}&_sacat=0"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = bs4.BeautifulSoup(res.text, "html.parser")
        
        # Skip the first element as it's often a hidden template on eBay
        for result in soup.select(".s-item__wrapper")[1:6]:
            title_tag = result.select_one(".s-item__title")
            if not title_tag or "Shop on eBay" in title_tag.text:
                continue
            title = title_tag.text
            link_tag = result.select_one(".s-item__link")
            link = link_tag["href"] if link_tag else ""
            
            price_tag = result.select_one(".s-item__price")
            price = extract_price(price_tag.text) if price_tag else None
            
            if price and price <= item["max_price"]:
                if evaluate_deal_with_llm(item["name"], title, price):
                    send_discord_alert(title, price, link, "eBay", item["name"])
    except Exception as e:
        print(f"[ERROR] eBay: {e}")

# ==============================================================================
# 4. MAIN EXECUTION
# ==============================================================================
def main():
    print("Starting AI-filtered deal scan...")
    for item in WATCHLIST:
        print(f"Scanning for: {item['name']}...")
        check_craigslist(item)
        check_us_audio_mart(item)
        check_reverb(item)
        check_ebay(item)
    print("Scan complete!")

if __name__ == "__main__":
    main()
