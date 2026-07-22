"""
eBay feed handler using eBay's official Browse API -- a free developer
account, OAuth client-credentials flow (no user login, no scraping).

Get keys: developer.ebay.com -> your app's Production Keyset. Set
EBAY_CLIENT_ID / EBAY_CLIENT_SECRET as environment variables (or GitHub
secrets). The access token is cached in-process and refreshed once it's
within 60 seconds of expiring.
"""

import base64
import logging
import os
import time

import requests

from config import (
    EBAY_CLIENT_ID_ENV,
    EBAY_CLIENT_SECRET_ENV,
    EBAY_MARKETPLACE_ID,
    TARGET_WATCHLIST,
)
from feeds.base import safe_get

logger = logging.getLogger(__name__)

PLATFORM_NAME = "eBay"
TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

_token_cache = {"access_token": None, "expires_at": 0}


def _get_access_token():
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    client_id = os.environ.get(EBAY_CLIENT_ID_ENV)
    client_secret = os.environ.get(EBAY_CLIENT_SECRET_ENV)
    if not (client_id and client_secret):
        return None

    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    body = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    }

    try:
        resp = requests.post(TOKEN_URL, headers=headers, data=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error("Failed to obtain eBay OAuth token: %s", e)
        return None

    _token_cache["access_token"] = data.get("access_token")
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 7200)
    return _token_cache["access_token"]


def fetch():
    listings = []
    token = _get_access_token()
    if token is None:
        logger.warning(
            "eBay credentials not set (env vars %s / %s) -- skipping eBay.",
            EBAY_CLIENT_ID_ENV, EBAY_CLIENT_SECRET_ENV,
        )
        return listings

    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": EBAY_MARKETPLACE_ID,
    }

    keywords = {t["keyword"] for t in TARGET_WATCHLIST}

    for keyword in keywords:
        resp = safe_get(SEARCH_URL, headers=headers, params={"q": keyword, "limit": 50})
        if resp is None:
            continue

        try:
            data = resp.json()
        except ValueError as e:
            logger.error("Failed to parse eBay JSON for '%s': %s", keyword, e)
            continue

        for item in data.get("itemSummaries", []):
            title = item.get("title", "")
            item_id = item.get("itemId")
            url = item.get("itemWebUrl", "")
            price_value = (item.get("price") or {}).get("value")

            if not (title and item_id and url):
                continue

            try:
                price = float(price_value) if price_value is not None else None
            except (TypeError, ValueError):
                price = None

            listings.append({
                "id": f"ebay_{item_id}",
                "title": title,
                "price": price,
                "url": url,
                "platform": PLATFORM_NAME,
            })

    logger.info("%s: fetched %d listing(s)", PLATFORM_NAME, len(listings))
    return listings
