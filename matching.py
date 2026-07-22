"""
Matching engine: price extraction with fallback strategies, and
positive/negative keyword matching against the watchlist.
"""

import logging
import re

from config import GLOBAL_NEGATIVE_KEYWORDS, TARGET_WATCHLIST

logger = logging.getLogger(__name__)

# Ordered from most to least specific. First match wins.
_PRICE_PATTERNS = [
    re.compile(r'\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)'),           # "$750" / "$1,200.00"
    re.compile(r'\bUSD\s*([0-9][0-9,]*(?:\.[0-9]{2})?)', re.I),  # "USD 750"
    re.compile(r'([0-9][0-9,]{2,})\s*(?:shipped|obo|firm|each)', re.I),  # "700 shipped"
    re.compile(r'\b([0-9]{3,5})\b'),                              # bare "750" fallback
]


def extract_price(text):
    """
    Attempts several regex strategies in priority order to pull a dollar
    amount out of a listing title. Returns a float, or None if nothing
    plausible was found.
    """
    if not text:
        return None

    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                value = float(raw)
            except ValueError:
                continue
            # Sanity bound: reject obvious junk (years, phone fragments, etc.)
            if 1 <= value <= 50000:
                return value

    return None


def _contains_any(haystack, needles):
    return any(needle.lower() in haystack for needle in needles if needle)


def is_target_match(item):
    """
    Evaluates a listing dict ({'title', 'price', ...}) against the
    watchlist. Applies global negative keywords first, then per-target
    positive keyword + price cap + per-target negative keywords.
    """
    title_lower = item["title"].lower()
    item_price = item.get("price")

    if _contains_any(title_lower, GLOBAL_NEGATIVE_KEYWORDS):
        return False

    for target in TARGET_WATCHLIST:
        if target["keyword"] not in title_lower:
            continue

        if _contains_any(title_lower, target.get("negative_keywords", [])):
            continue

        max_price = target.get("max_price")
        if max_price is None or item_price is None or item_price <= max_price:
            return True

        logger.debug(
            "Matched keyword '%s' but price %s exceeds cap %s: %s",
            target["keyword"], item_price, max_price, item["title"],
        )

    return False
