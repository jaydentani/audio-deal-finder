"""
Headless-browser fallback for sources sitting behind a Cloudflare JS
challenge that a plain `requests.get()` can't get past (confirmed on
US Audio Mart and Craigslist via the `cf-mitigated: challenge` response
header -- this happens from every IP, not just GitHub Actions runners).

Requires:
    pip install playwright
    playwright install --with-deps chromium

Honest limits, worth knowing before relying on this:
  - Much heavier than a plain GET: launches a real Chromium process per
    call, adding a few seconds per fetch instead of milliseconds. That's
    fine at a 20-minute polling interval, but it's not free in the
    "instant" sense.
  - NOT guaranteed to work. Cloudflare's *managed* challenge usually
    auto-resolves once real browser JS executes, which this handles. But
    if a site escalates to an *interactive* Turnstile challenge (a click
    or puzzle), a headless browser alone won't solve it -- that needs
    either a human in the loop or a paid CAPTCHA-solving service, which
    is intentionally out of scope here.
  - Repeated automated hits, even from a real browser, can still get a
    given IP flagged over time by Cloudflare's bot-management scoring.

This is used as a fallback only: feeds try a fast `requests.get()` first
(see feeds/base.py get_raw) and only reach for this when that request
comes back with Cloudflare's challenge marker.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

_STEALTH_ARGS = ["--disable-blink-features=AutomationControlled"]

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_CHALLENGE_MARKERS = ("Just a moment", "Attention Required", "Checking your browser")


def is_cloudflare_challenge(response):
    """Detects Cloudflare's challenge marker on a `requests` Response."""
    if response is None:
        return False
    cf_mitigated = response.headers.get("cf-mitigated", "")
    return response.status_code == 403 and "challenge" in cf_mitigated


def fetch_rendered_text(url, wait_ms=6000, user_agent=None):
    """
    Loads `url` in headless Chromium, waits for Cloudflare's challenge to
    (hopefully) auto-resolve, and returns the final page's raw text
    content. Returns None if Playwright isn't installed or the fetch
    still looks like an unresolved challenge page.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning(
            "Playwright not installed -- skipping browser fallback for %s. "
            "Run: pip install playwright && playwright install --with-deps chromium",
            url,
        )
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=_STEALTH_ARGS)
            context = browser.new_context(
                user_agent=user_agent or _DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(wait_ms)  # let the challenge auto-resolve/redirect

            text = page.evaluate("document.documentElement.textContent") or ""
            browser.close()

            if text and not any(marker in text for marker in _CHALLENGE_MARKERS):
                return text

            logger.warning("Browser fetch for %s still looks like a challenge page", url)
            return None
    except Exception as e:
        logger.error("Playwright fetch failed for %s: %s", url, e)
        return None
