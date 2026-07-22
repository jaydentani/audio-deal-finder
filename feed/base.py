"""
Shared helpers for feed handlers. Every feed module exposes a single
fetch() -> list[dict] function returning items shaped as:

    {"id": str, "title": str, "price": float|None, "url": str, "platform": str}
"""

import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def safe_get(url, headers=None, timeout=10, params=None):
    """GET with consistent error handling/logging. Returns Response or None."""
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, params=params)
        if resp.status_code != 200:
            logger.warning("GET %s returned status %s", url, resp.status_code)
            return None
        return resp
    except requests.RequestException as e:
        logger.error("Request failed for %s: %s", url, e)
        return None
