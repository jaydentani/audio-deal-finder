"""Discord webhook notification sender."""

import logging
import os

import requests

from config import DISCORD_WEBHOOK_URL_ENV

logger = logging.getLogger(__name__)

EMERALD_GREEN = 3066993


def send_discord_alert(item):
    """Sends a rich embed notification to the configured Discord webhook."""
    webhook_url = os.environ.get(DISCORD_WEBHOOK_URL_ENV)
    price_str = f"${item['price']:,.2f}" if item.get("price") else "Check Listing"

    payload = {
        "embeds": [{
            "title": f"🚨 Deal Match: {item['title']}",
            "url": item["url"],
            "color": EMERALD_GREEN,
            "fields": [
                {"name": "Price", "value": price_str, "inline": True},
                {"name": "Platform", "value": item.get("platform", "Audio Marketplace"), "inline": True},
            ],
            "footer": {"text": "Audio Deal Finder • Live Alert"},
        }]
    }

    if not webhook_url:
        logger.info("[TEST MODE - no webhook set] Match: %s | %s | %s",
                    item["title"], price_str, item["url"])
        return

    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        if res.status_code == 204:
            logger.info("Sent Discord alert for: %s", item["title"])
        else:
            logger.warning("Discord webhook returned status %s", res.status_code)
    except requests.RequestException as e:
        logger.error("Failed to send Discord alert: %s", e)
