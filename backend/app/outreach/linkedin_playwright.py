"""LinkedIn outreach via headless Playwright (DOM-based, safe for POST actions).

Why DOM, not Voyager API?
- LinkedIn actively flags undocumented POST requests (send message, connect).
- DOM interaction mimics a real user browsing, which is much harder to detect.
- We still use the li_at cookie so no password is stored.

Anti-ban strategy:
- Randomised delays between every DOM action (type, click, navigate).
- Per-worker rate limit: at most 1 message every LI_MIN_DELAY..LI_MAX_DELAY seconds.
- Stealth args to hide the headless Chromium fingerprint.
- Runs non-headless can be toggled via LI_HEADLESS env var for debugging.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Rate-limit state (module-level — shared within one Celery worker process)
# ---------------------------------------------------------------------------

_LI_RATE_LOCK_KEY = "li_sender_last_send"
_last_li_send: float = 0.0


def _li_rate_wait() -> None:
    """Block until the minimum inter-message delay has elapsed."""
    global _last_li_send
    min_delay = settings.li_send_min_delay
    max_delay = settings.li_send_max_delay
    target = random.uniform(min_delay, max_delay)
    elapsed = time.monotonic() - _last_li_send
    if elapsed < target:
        wait = target - elapsed
        log.debug("LinkedIn rate-limit: sleeping %.1fs before next send", wait)
        time.sleep(wait)
    _last_li_send = time.monotonic()


def _human_delay(min_s: float = 0.8, max_s: float = 2.5) -> None:
    """Short randomised pause to mimic human reading/typing time."""
    time.sleep(random.uniform(min_s, max_s))


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

def _get_browser_context():
    """Return a synchronous Playwright browser context with stealth settings."""
    from playwright.sync_api import sync_playwright  # lazy import

    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=settings.li_headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
        ],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        timezone_id="Europe/Berlin",
    )
    # Inject li_at cookie so we're logged in as the account holder
    context.add_cookies(
        [
            {
                "name": "li_at",
                "value": settings.linkedin_li_at,
                "domain": ".linkedin.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }
        ]
    )
    # Basic stealth: remove the webdriver property
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return p, browser, context


def _close_browser(p, browser) -> None:
    try:
        browser.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        p.stop()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Core send logic
# ---------------------------------------------------------------------------

def _send_via_messaging_overlay(page, linkedin_url: str, message: str) -> None:
    """Open the candidate's profile and send a message via the messaging overlay."""
    # Navigate to the profile
    page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30_000)
    _human_delay(2.0, 4.0)

    # Try to click the "Message" button on the profile page
    msg_button_selectors = [
        "a[href*='/messaging/compose/']",
        "button[aria-label^='Message']",
        "button:has-text('Message')",
        ".pvs-profile-actions button:has-text('Message')",
        "a:has-text('Message')",
        ".pvs-profile-actions a:has-text('Message')",
        ".pvs-profile-actions >> text='Message'"
    ]
    clicked = False
    for sel in msg_button_selectors:
        button = page.locator(sel).first
        if button.is_visible():
            try:
                href = button.get_attribute("href")
                if href and href.startswith("/"):
                    target_url = f"https://www.linkedin.com{href}"
                    log.info("Navigating directly to message compose URL: %s", target_url)
                    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                else:
                    # Use JS click to bypass any overlay intercepting pointer events
                    button.evaluate("node => node.click()")
                    log.info("Clicked message button using selector via JS: %s", sel)
                clicked = True
                break
            except Exception as e:
                log.warning("Could not interact with selector %s: %s", sel, e)

    if not clicked:
        raise RuntimeError(f"Could not find 'Message' button on profile: {linkedin_url}")

    _human_delay(1.5, 3.0)

    # Locate the compose textarea inside the messaging overlay or full page
    compose_selectors = [
        "div.msg-form__contenteditable[contenteditable='true']",
        "div[role='textbox'][aria-label='Write a message…']",
        "div[data-artdeco-is-focused] div[contenteditable='true']",
    ]
    textarea = None
    for sel in compose_selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=10_000)
            textarea = loc
            break
        except Exception:  # noqa: BLE001
            continue

    if textarea is None:
        raise RuntimeError("Could not locate messaging compose textarea")

    textarea.click()
    _human_delay(0.5, 1.2)

    # Type message with human-like speed (random delay between chunks)
    words = message.split(" ")
    for i, word in enumerate(words):
        chunk = word if i == 0 else " " + word
        textarea.type(chunk, delay=random.randint(30, 90))
        if random.random() < 0.15:  # occasional longer pause mid-typing
            _human_delay(0.3, 0.9)

    _human_delay(1.0, 2.5)

    # Click Send
    send_selectors = [
        "button.msg-form__send-button",
        "button[type='submit']:has-text('Send')",
        "button[aria-label='Send']",
    ]
    sent = False
    for sel in send_selectors:
        try:
            send_btn = page.locator(sel).first
            if send_btn.is_enabled(timeout=3_000):
                send_btn.click()
                sent = True
                log.debug("Clicked Send button via selector: %s", sel)
                break
        except Exception:  # noqa: BLE001
            continue

    if not sent:
        raise RuntimeError("Could not locate or click the Send button")

    _human_delay(1.5, 3.0)  # wait for the message to be delivered


# ---------------------------------------------------------------------------
# Public API (mirrors the Phantombuster interface)
# ---------------------------------------------------------------------------

def send_linkedin_playwright(linkedin_url: str, message: str) -> dict[str, Any]:
    """Send a LinkedIn message to a profile URL using a headless Playwright browser.

    Enforces a randomised inter-send delay to avoid rate-limiting.
    Returns: {success: bool, error: str | None, sent_at: str | None}
    """
    if not settings.linkedin_li_at:
        return {
            "success": False,
            "error": "LINKEDIN_LI_AT cookie not configured",
            "sent_at": None,
        }

    # Enforce inter-message rate limit BEFORE opening browser
    _li_rate_wait()

    p = browser = context = page = None
    try:
        p, browser, context = _get_browser_context()
        page = context.new_page()

        _send_via_messaging_overlay(page, linkedin_url, message)

        sent_at = datetime.now(tz=timezone.utc).isoformat()
        log.info("LinkedIn Playwright: message sent to %s", linkedin_url)
        return {"success": True, "error": None, "sent_at": sent_at}

    except Exception as exc:  # noqa: BLE001
        log.exception("LinkedIn Playwright send failed for %s", linkedin_url)
        error_msg = str(exc)

        # Detect auth/cookie failure and surface it clearly
        if any(kw in error_msg.lower() for kw in ("authwall", "login", "session", "unauthorized")):
            error_msg = f"COOKIE_EXPIRED: {error_msg}"

        return {"success": False, "error": error_msg, "sent_at": None}

    finally:
        if page:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
        if context:
            try:
                context.close()
            except Exception:  # noqa: BLE001
                pass
        if browser and p:
            _close_browser(p, browser)
