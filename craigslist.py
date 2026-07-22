"""
Craigslist feed handler.

Craigslist search results support &format=rss, which is a free, no-auth
way to poll listings. Since Craigslist's query syntax doesn't reliably
support OR across multiple keywords, this runs one search per
(region, watchlist keyword) pair -- more requests, but each is cheap and
free. CRAIGSLIST_REQUEST_DELAY_SECONDS throttles the loop so this stays
polite and avoids tripping any rate limiting.
"""

import logging
import time
import xml.etree.ElementTree as ET

from config import (
    CRAIGSLIST_CATEGORY,
    CRAIGSLIST_REGIONS,
    CRAIGSLIST_REQUEST_DELAY_SECONDS,
    TARGET_WATCHLIST,
)
from feeds.base import DEFAULT_USER_AGENT, safe_get
from matching import extract_price

logger = logging.getLogger(__name__)

# Craigslist's RSS namespace for extra fields (price lives here sometimes)
_NS = {"rss": "http://purl.org/rss/1.0/"}


def _build_url(region, keyword):
    return f"https://{region}.craigslist.org/search/{CRAIGSLIST_CATEGORY}"


def fetch():
    listings = []
    keywords = [t["keyword"] for t in TARGET_WATCHLIST]

    for region in CRAIGSLIST_REGIONS:
        for keyword in keywords:
            url = _build_url(region, keyword)
            resp = safe_get(
                url,
                headers={"User-Agent": DEFAULT_USER_AGENT},
                params={"query": keyword, "sort": "date", "format": "rss"},
            )
            time.sleep(CRAIGSLIST_REQUEST_DELAY_SECONDS)

            if resp is None:
                continue

            try:
                root = ET.fromstring(resp.content)
            except ET.ParseError as e:
                logger.error("Failed to parse Craigslist RSS (%s/%s): %s", region, keyword, e)
                continue

            # Craigslist RSS items are RSS 1.0 style <item> tags at the root
            items = root.findall(".//item") or root.findall(".//rss:item", _NS)

            for entry in items:
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
