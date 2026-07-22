"""US Audio Mart RSS feed handler, with a Cloudflare-challenge fallback."""

import logging
import xml.etree.ElementTree as ET

from config import USAUDIOMART_RSS_URL, BROWSER_CHALLENGE_WAIT_MS
from feeds.base import DEFAULT_USER_AGENT, get_raw
from feeds.browser_fetch import fetch_rendered_text, is_cloudflare_challenge
from matching import extract_price

logger = logging.getLogger(__name__)

PLATFORM_NAME = "US Audio Mart"


def _get_feed_text():
    resp = get_raw(USAUDIOMART_RSS_URL, headers={"User-Agent": DEFAULT_USER_AGENT})

    if resp is not None and resp.status_code == 200:
        return resp.text

    if is_cloudflare_challenge(resp):
        logger.info("%s: hit a Cloudflare challenge, falling back to headless browser", PLATFORM_NAME)
        return fetch_rendered_text(USAUDIOMART_RSS_URL, wait_ms=BROWSER_CHALLENGE_WAIT_MS)

    if resp is not None:
        logger.warning("%s: GET returned status %s", PLATFORM_NAME, resp.status_code)
    return None


def fetch():
    listings = []
    text = _get_feed_text()
    if not text:
        return listings

    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        logger.error("Failed to parse %s RSS: %s", PLATFORM_NAME, e)
        return listings

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
            "platform": PLATFORM_NAME,
        })

    logger.info("%s: fetched %d listing(s)", PLATFORM_NAME, len(listings))
    return listings
