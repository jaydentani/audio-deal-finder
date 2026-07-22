"""
Audio Deal Finder Bot -- main entrypoint.

Pulls listings from every active feed (feeds/__init__.py), filters them
through the matching engine, deduplicates against seen_listings.json,
and fires Discord alerts for new matches.

Usage:
    python bot.py
"""

import logging

from feeds import ACTIVE_FEEDS
from matching import is_target_match
from notifier import send_discord_alert
from storage import load_seen_ids, save_seen_ids

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


def fetch_all_listings():
    """Runs every registered feed handler and combines the results."""
    all_listings = []
    for feed_module in ACTIVE_FEEDS:
        try:
            all_listings.extend(feed_module.fetch())
        except Exception as e:  # a single bad feed shouldn't kill the run
            logger.exception("Feed handler %s raised an exception: %s", feed_module.__name__, e)
    return all_listings


def main():
    logger.info("Starting deal scan...")

    seen_ids = load_seen_ids()
    scraped_items = fetch_all_listings()
    new_alerts = 0

    for item in scraped_items:
        item_id = item.get("id") or item.get("url")
        if not item_id or item_id in seen_ids:
            continue

        seen_ids.add(item_id)

        if is_target_match(item):
            send_discord_alert(item)
            new_alerts += 1

    save_seen_ids(seen_ids)
    logger.info("Scan complete. Inspected %d item(s). Sent %d new alert(s).",
                len(scraped_items), new_alerts)


if __name__ == "__main__":
    main()
