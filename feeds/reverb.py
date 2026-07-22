"""
Reverb.com feed handler using Reverb's official public API -- a free
personal access token, no scraping, no ToS risk.

Get a token: reverb.com -> Settings -> Advanced -> API Tokens, then set
it as the REVERB_ACCESS_TOKEN environment variable (or GitHub secret).
"""

import logging
import os

from config import REVERB_ACCESS_TOKEN_ENV, TARGET_WATCHLIST
from feeds.base import safe_get

logger = logging.getLogger(__name__)

PLATFORM_NAME = "Reverb"
API_URL = "https://api.reverb.com/api/listings"


def _headers():
    token = os.environ.get(REVERB_ACCESS_TOKEN_ENV)
    if not token:
        return None
    return {
        "Accept": "application/hal+json",
        "Accept-Version": "3.0",
        "Authorization": f"Bearer {token}",
    }


def fetch():
    listings = []
    headers = _headers()
    if headers is None:
        logger.warning(
            "%s access token not set (env var %s) -- skipping Reverb.",
            PLATFORM_NAME, REVERB_ACCESS_TOKEN_ENV,
        )
        return listings

    # Reverb's search doesn't reliably OR multiple terms, so search once
    # per unique watchlist keyword, same pattern as Craigslist.
    keywords = {t["keyword"] for t in TARGET_WATCHLIST}

    for keyword in keywords:
        resp = safe_get(API_URL, headers=headers, params={"query": keyword, "per_page": 50})
        if resp is None:
            continue

        try:
            data = resp.json()
        except ValueError as e:
            logger.error("Failed to parse Reverb JSON for '%s': %s", keyword, e)
            continue

        for listing in data.get("listings", []):
            title = listing.get("title", "")
            listing_id = listing.get("id")
            url = listing.get("_links", {}).get("web", {}).get("href", "")
            price_amount = (listing.get("price") or {}).get("amount")

            if not (title and listing_id and url):
                continue

            try:
                price = float(price_amount) if price_amount is not None else None
            except (TypeError, ValueError):
                price = None

            listings.append({
                "id": f"reverb_{listing_id}",
                "title": title,
                "price": price,
                "url": url,
                "platform": PLATFORM_NAME,
            })

    logger.info("%s: fetched %d listing(s)", PLATFORM_NAME, len(listings))
    return listings
