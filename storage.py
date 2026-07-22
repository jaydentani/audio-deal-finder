"""
Persistent storage for previously-seen listing IDs.

Design note on the git-bloat problem:
-------------------------------------
The old approach committed seen_listings.json back to the repo on every
run, which grows the git history forever for a file that's really just
ephemeral cache state. Instead:

  * Locally (Mac/launchd/cron): SEEN_FILE just lives on disk. No git
    involved at all -- this module doesn't know or care about git.
  * On GitHub Actions: use actions/cache (see .github/workflows/main.yml)
    to persist SEEN_FILE across runs, keyed on a stable cache key. The
    workflow restores it before the run and saves it after. Nothing is
    ever committed, so the repo's git history stays clean.

This module is intentionally storage-agnostic -- it just reads/writes a
JSON file at a path. Where that path lives (local disk vs. a cache
restored by CI) is someone else's problem.
"""

import json
import logging
import os

from config import MAX_SEEN_ITEMS, SEEN_FILE

logger = logging.getLogger(__name__)


def load_seen_ids(path=SEEN_FILE):
    """Loads previously notified listing IDs from local JSON storage."""
    if not os.path.exists(path):
        return set()

    try:
        with open(path, "r") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read %s (%s). Starting fresh.", path, e)
        return set()


def save_seen_ids(seen_ids, path=SEEN_FILE, max_items=MAX_SEEN_ITEMS):
    """Saves the updated set of listing IDs, capped to a rolling window."""
    seen_list = list(seen_ids)[-max_items:]
    try:
        with open(path, "w") as f:
            json.dump(seen_list, f, indent=2)
    except OSError as e:
        logger.error("Error saving %s: %s", path, e)
