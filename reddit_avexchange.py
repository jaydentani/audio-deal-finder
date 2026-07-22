"""
Reddit feed handler (e.g. r/AVexchange).

Uses Reddit's public JSON endpoint rather than scraping HTML. Reddit is
strict about User-Agent -- a generic browser UA gets you 429'd quickly,
so this uses a descriptive one (see config.REDDIT_USER_AGENT). Update
that string with your own Reddit username per Reddit's API etiquette,
even though this hits the unauthenticated public JSON endpoint.
"""

import logging

from config import REDDIT_SUBREDDITS, REDDIT_USER_AGENT
from feeds.base import safe_get
from matching import extract_price

logger = logging.getLogger(__name__)

PLATFORM_NAME_TEMPLATE = "Reddit r/{sub}"


def fetch():
    listings = []

    for sub in REDDIT_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/new.json"
        resp = safe_get(url, headers={"User-Agent": REDDIT_USER_AGENT}, params={"limit": 50})
        if resp is None:
            continue

        try:
            data = resp.json()
        except ValueError as e:
            logger.error("Failed to parse Reddit JSON for r/%s: %s", sub, e)
            continue

        children = data.get("data", {}).get("children", [])
        platform = PLATFORM_NAME_TEMPLATE.format(sub=sub)

        for child in children:
            post = child.get("data", {})
            title = post.get("title", "")
            permalink = post.get("permalink", "")
            post_id = post.get("id", "")

            if not (title and permalink and post_id):
                continue

            url_full = f"https://www.reddit.com{permalink}"

            listings.append({
                "id": f"reddit_{post_id}",
                "title": title,
                "price": extract_price(title),
                "url": url_full,
                "platform": platform,
            })

        logger.info("%s: fetched %d listing(s)", platform, len(children))

    return listings
