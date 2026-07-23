"""Reddit feed handler (e.g. r/AVexchange)."""

import logging

from config import REDDIT_SUBREDDITS
from feeds.base import get_raw
from matching import extract_price

logger = logging.getLogger(__name__)

PLATFORM_NAME_TEMPLATE = "Reddit r/{sub}"

# Disguise the request as a normal browser accessing the JSON endpoint
REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}

def fetch():
    listings = []

    for sub in REDDIT_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/new.json"
        resp = get_raw(url, headers=REDDIT_HEADERS, params={"limit": 50})
        
        if resp is None or resp.status_code != 200:
            status = resp.status_code if resp else "Connection Error"
            logger.warning("Reddit r/%s: GET returned status %s", sub, status)
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