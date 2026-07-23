"""Craigslist feed handler, with a Cloudflare-challenge fallback."""

import logging
import time
import xml.etree.ElementTree as ET

from config import (
    BROWSER_CHALLENGE_WAIT_MS,
    CRAIGSLIST_CATEGORY,
    CRAIGSLIST_REGIONS,
    CRAIGSLIST_REQUEST_DELAY_SECONDS,
    TARGET_WATCHLIST,
)
from feeds.base import DEFAULT_USER_AGENT, get_raw
from feeds.browser_fetch import fetch_rendered_text, is_cloudflare_challenge
from matching import extract_price

logger = logging.getLogger(__name__)


def _build_url(region):
    return f"https://{region}.craigslist.org/search/{CRAIGSLIST_CATEGORY}"


def _get_search_text(region, keyword):
    url = _build_url(region)
    params = {"query": keyword, "sort": "date", "format": "rss"}
    
    # Pass full browser headers to avoid Craigslist WAF blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = get_raw(url, headers=headers, params=params)

    if resp is not None and resp.status_code == 200:
        return resp.text

    if is_cloudflare_challenge(resp) or (resp is not None and resp.status_code == 403):
        logger.info("Craigslist (%s/%s): Blocked (403 or CF challenge), falling back to browser", region, keyword)
        full_url = resp.url if resp else url
        return fetch_rendered_text(full_url, wait_ms=BROWSER_CHALLENGE_WAIT_MS)

    if resp is not None:
        logger.warning("Craigslist (%s/%s): GET returned status %s", region, keyword, resp.status_code)
    return None


def fetch():
    listings = []
    keywords = [t["keyword"] for t in TARGET_WATCHLIST]

    for region in CRAIGSLIST_REGIONS:
        for keyword in keywords:
            text = _get_search_text(region, keyword)
            time.sleep(CRAIGSLIST_REQUEST_DELAY_SECONDS)

            if not text or not text.strip().startswith(("<?xml", "<rss", "<feed")):
                logger.warning("Craigslist (%s/%s): Payload is not valid XML (likely an HTML bot block page). Skipping.", region, keyword)
                continue
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
