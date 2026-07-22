"""US Audio Mart RSS feed handler."""

import logging
import xml.etree.ElementTree as ET

from config import USAUDIOMART_RSS_URL
from feeds.base import DEFAULT_USER_AGENT, safe_get
from matching import extract_price

logger = logging.getLogger(__name__)

PLATFORM_NAME = "US Audio Mart"


def fetch():
    listings = []
    resp = safe_get(USAUDIOMART_RSS_URL, headers={"User-Agent": DEFAULT_USER_AGENT})
    if resp is None:
        return listings

    try:
        root = ET.fromstring(resp.content)
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
