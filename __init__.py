"""
Feed registry. To add a new source: write a module with a fetch() function
returning a list of listing dicts, then add it to ACTIVE_FEEDS below.
"""

from feeds import craigslist, reddit_avexchange, usaudiomart

ACTIVE_FEEDS = [
    usaudiomart,
    reddit_avexchange,
    craigslist,
]
