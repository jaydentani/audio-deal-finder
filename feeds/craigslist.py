"""Craigslist feed handler."""

import logging
import time
import xml.etree.ElementTree as ET

from config import (
    CRAIGSLIST_CATEGORY,
    CRAIGSLIST_REGIONS,
    CRAIGSLIST_REQUEST_DELAY_SECONDS,
    TARGET_WATCHLIST,
)
from feeds.base import get_raw
from matching import extract_price

logger = logging.getLogger(__name__)

# Pristine browser headers to bypass the WAF
CRAIGSLIST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

def _build_url(region):
    return f"https://{region}.craigslist.org/search/{CRAIGSLIST_CATEGORY}"

def _get_search_text(region, keyword):
    url = _build_url(region)
    params = {"query": keyword, "sort": "date", "format": "rss"}
    
    resp = get_raw(url, headers=CRAIGSLIST_HEADERS, params=params)

    if resp is not None and resp.status_code == 200:
        return resp.text

    if resp is not None:
        logger.warning("Craigslist (%s/%s): GET returned status %s", region, keyword, resp.status_code)
    return None

def fetch():
    listings = []
    keywords = [t["keyword"] for t in TARGET_WATCHLIST]

    for region in CRAIGSLIST_REGIONS:
        for keyword in keywords:
            text = _get_search_text(region, keyword)
            
            # Critical: Sleep to prevent IP bans during the loop
            time.sleep(CRAIGSLIST_REQUEST_DELAY_SECONDS)

            if not text:
                continue

            try:
                root = ET.fromstring(text)
            except ET.ParseError as e:
                logger.error("Failed to parse Craigslist RSS (%s/%s): %s", region, keyword, e)
                continue

            for entry in root.findall(".//item"):
                title_el = entry.find("title")
                link_el = entry.find("link")
                title = title_el.text if title_el is not None else ""
                link = link_el.text if link_el is not None else ""

                if not (title and link):
                    continue

                listings.append({
                    "id": link,
                    "title": title,
                    "price": extract_price(title),
                    "url": link,
                    "platform": f"Craigslist ({region})",
                })

    logger.info("Craigslist: fetched %d listing(s) across %d region(s)",
                len(listings), len(CRAIGSLIST_REGIONS))
    return listings