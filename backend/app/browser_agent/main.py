"""Persistent Chromium controller displayed through local noVNC."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from app.scrapers.linkedin_salesnav import SalesNavScraper


AGENT_TOKEN = os.getenv("BROWSER_AGENT_TOKEN", "local-browser-agent")
PROFILE_DIR = Path(os.getenv("BROWSER_PROFILE_DIR", "/browser-data/profile"))
EXECUTABLE = os.getenv("BROWSER_EXECUTABLE_PATH", "/usr/bin/chromium")


class SessionPayload(BaseModel):
    session_id: str
    url: Optional[str] = None
    cursor: dict[str, Any] = Field(default_factory=dict)
    text: Optional[str] = Field(None, max_length=4096)
    key: Optional[str] = None


@dataclass
class ManagedSession:
    session_id: str
    playwright: Playwright
    context: BrowserContext
    page: Page
    manual_control: bool = True


sessions: dict[str, ManagedSession] = {}
app = FastAPI(title="Sourcer Browser Agent", version="1.0.0")


def authorize(x_browser_agent_token: str = Header("")) -> None:
    if x_browser_agent_token != AGENT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid browser agent token")


def _session(session_id: str) -> ManagedSession:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Browser session not running")
    return session


def _auth_required(url: str) -> bool:
    return any(part in url for part in ("/login", "/authwall", "/checkpoint/", "/challenge/"))


async def _salesnav_rate_limited(page: Page) -> bool:
    """Detect LinkedIn's explicit throttling page before parsing cards."""
    try:
        return await page.get_by_text("Too Many Requests", exact=True).count() > 0
    except Exception:
        return False


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "sessions": len(sessions)}


@app.post("/sessions/start", dependencies=[Depends(authorize)])
async def start_session(payload: SessionPayload) -> dict[str, Any]:
    existing = sessions.get(payload.session_id)
    if existing:
        return {"state": "ready", "current_url": existing.page.url}
    if sessions:
        # Local V1 intentionally owns one visible persistent profile.
        old = next(iter(sessions.values()))
        await old.context.close()
        await old.playwright.stop()
        sessions.clear()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    playwright = await async_playwright().start()
    launch_options = {
        "user_data_dir": str(PROFILE_DIR),
        "headless": False,
        "executable_path": EXECUTABLE if Path(EXECUTABLE).exists() else None,
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-US",
        "timezone_id": "Europe/Warsaw",
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-password-manager-reauthentication",
            "--password-store=basic",
            "--no-first-run",
            "--window-position=0,0",
            "--window-size=1440,900",
        ],
    }
    try:
        context = await playwright.chromium.launch_persistent_context(**launch_options)
    except Exception:
        # Chromium can retain these process-singleton links after an abrupt
        # container replacement.  Retrying once is safe because this service
        # owns the one persistent profile and there is no active context.
        for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            (PROFILE_DIR / lock_name).unlink(missing_ok=True)
        context = await playwright.chromium.launch_persistent_context(**launch_options)
    page = context.pages[0] if context.pages else await context.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    sessions[payload.session_id] = ManagedSession(payload.session_id, playwright, context, page)
    if payload.url and payload.url.startswith("https://www.linkedin.com/"):
        await page.goto(payload.url, wait_until="domcontentloaded", timeout=60_000)
    awaiting_auth = _auth_required(page.url)
    return {
        "state": "awaiting_auth" if awaiting_auth else "ready",
        "current_url": page.url,
        "awaiting_auth": awaiting_auth,
    }


@app.post("/sessions/open", dependencies=[Depends(authorize)])
async def open_url(payload: SessionPayload) -> dict[str, Any]:
    session = _session(payload.session_id)
    if not payload.url or not payload.url.startswith("https://www.linkedin.com/"):
        raise HTTPException(status_code=400, detail="Only LinkedIn HTTPS URLs are accepted")
    await session.page.goto(payload.url, wait_until="domcontentloaded", timeout=60_000)
    session.manual_control = True
    return {
        "state": "awaiting_auth" if _auth_required(session.page.url) else "manual_control",
        "current_url": session.page.url,
        "awaiting_auth": _auth_required(session.page.url),
    }


@app.post("/sessions/search", dependencies=[Depends(authorize)])
async def run_keyword_search(payload: SessionPayload) -> dict[str, Any]:
    session = _session(payload.session_id)
    if not payload.text:
        raise HTTPException(status_code=400, detail="Search keywords required")
    if _auth_required(session.page.url):
        return {
            "state": "awaiting_auth",
            "current_url": session.page.url,
            "awaiting_auth": True,
        }
    if "/sales/search/people" not in session.page.url:
        await session.page.goto(
            "https://www.linkedin.com/sales/search/people",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
    keyword_input = session.page.get_by_placeholder("Search keywords", exact=True)
    if await keyword_input.count() != 1:
        raise HTTPException(status_code=409, detail="Sales Navigator keyword field not found")
    await keyword_input.fill(payload.text)
    await keyword_input.press("Enter")
    await session.page.wait_for_timeout(1_500)
    session.manual_control = True
    return {
        "state": "manual_control",
        "current_url": session.page.url,
        "awaiting_auth": _auth_required(session.page.url),
    }


@app.post("/sessions/filter-options", dependencies=[Depends(authorize)])
async def inspect_filter_options(payload: SessionPayload) -> dict[str, Any]:
    """Return bounded visible filter controls for selector diagnostics."""
    session = _session(payload.session_id)
    page = session.page
    if payload.text:
        expand = page.get_by_role(
            "button",
            name=f"Expand {payload.text} filter",
            exact=True,
        )
        if await expand.count() != 1:
            raise HTTPException(status_code=409, detail=f"{payload.text} filter not found")
        if await expand.get_attribute("aria-expanded") != "true":
            await expand.click()
    query = str(payload.cursor.get("query") or "").strip()
    placeholder = str(payload.cursor.get("placeholder") or "").strip()
    if query and placeholder:
        filter_input = page.get_by_placeholder(placeholder, exact=True)
        if await filter_input.count() != 1:
            raise HTTPException(status_code=409, detail=f"{placeholder} input not found")
        await filter_input.click()
        await filter_input.fill("")
        await filter_input.type(query, delay=35)
        await page.wait_for_timeout(800)
    controls = await page.locator(
        "button, input, label, [role=button], [role=checkbox], [role=option]"
    ).evaluate_all(
        """elements => elements.map((element) => ({
          tag: element.tagName,
          text: (element.innerText || element.getAttribute('aria-label') || '').trim().slice(0, 160),
          placeholder: element.getAttribute('placeholder') || '',
          role: element.getAttribute('role') || '',
          ariaLabel: element.getAttribute('aria-label') || '',
          ariaExpanded: element.getAttribute('aria-expanded') || '',
          dataTestId: element.getAttribute('data-testid') || ''
        })).filter(item => item.text || item.placeholder || item.ariaLabel).slice(0, 240)"""
    )
    return {"current_url": page.url, "controls": controls}


@app.post("/sessions/search-summary", dependencies=[Depends(authorize)])
async def search_summary(payload: SessionPayload) -> dict[str, Any]:
    """Read visible result count without issuing another LinkedIn search."""
    session = _session(payload.session_id)
    if "/sales/search/people" not in session.page.url:
        raise HTTPException(status_code=409, detail="Open a Sales Navigator people search first")
    text = await session.page.locator("body").inner_text()
    match = re.search(r"(\d[\d,.]*\+?)\s+results", text, flags=re.IGNORECASE)
    return {
        "current_url": session.page.url,
        "result_count": match.group(1) if match else None,
    }


async def _expand_filter(page: Page, name: str) -> None:
    expand = page.get_by_role("button", name=f"Expand {name} filter", exact=True)
    collapse = page.get_by_role("button", name=f"Collapse {name} filter", exact=True)
    if await collapse.count() == 1:
        return
    if await expand.count() != 1:
        raise HTTPException(status_code=409, detail=f"{name} filter not found")
    await expand.click()


async def _include_typeahead(
    page: Page,
    *,
    filter_name: str,
    selected_filter_name: str,
    placeholder: str,
    query: str,
    expected_prefix: str,
) -> str:
    selected = page.get_by_role(
        "button",
        name=f"Remove {selected_filter_name} filter: “{query}”",
        exact=True,
    )
    if await selected.count() == 1:
        return f"{query} (already applied)"
    await _expand_filter(page, filter_name)
    filter_input = page.get_by_placeholder(placeholder, exact=True)
    if await filter_input.count() != 1:
        raise HTTPException(status_code=409, detail=f"{placeholder} input not found")
    await filter_input.click()
    await filter_input.fill("")
    await filter_input.type(query, delay=35)
    await page.wait_for_timeout(700)
    option = page.locator(
        f'[role="option"][aria-label^="Include “{expected_prefix}"]'
    )
    count = await option.count()
    if count != 1:
        raise HTTPException(
            status_code=409,
            detail=f"Expected one {expected_prefix} option, found {count}",
        )
    label = await option.get_attribute("aria-label") or expected_prefix
    await option.click()
    await page.wait_for_timeout(700)
    return label


@app.post("/sessions/apply-filters", dependencies=[Depends(authorize)])
async def apply_filters(payload: SessionPayload) -> dict[str, Any]:
    session = _session(payload.session_id)
    page = session.page
    if _auth_required(page.url):
        return {
            "state": "awaiting_auth",
            "current_url": page.url,
            "awaiting_auth": True,
        }
    plan = payload.cursor or {}
    applied: list[str] = []
    warnings: list[str] = []

    async def optional(step: str, action) -> None:
        try:
            applied.append(await action)
        except HTTPException as exc:
            warnings.append(f"{step} not applied: {exc.detail}")

    title = str(plan.get("current_title") or "").strip()
    if title:
        await optional("Current job title", _include_typeahead(
            page,
            filter_name="Current job title",
            selected_filter_name="Current job title",
            placeholder="Add current titles",
            query=title,
            expected_prefix=title,
        ))

    function_name = str(plan.get("function") or "").strip()
    if function_name:
        selected_function = page.get_by_role(
            "button",
            name=f"Remove Function filter: “{function_name}”",
            exact=True,
        )
        if await selected_function.count() == 1:
            applied.append(f"{function_name} (already applied)")
        else:
            add_function = page.locator(
                f'button[aria-label^="Add {function_name} "]'
            )
            if await add_function.count() == 1:
                try:
                    await add_function.click()
                    await page.wait_for_timeout(700)
                    applied.append(function_name)
                except Exception as exc:
                    warnings.append(f"Function not applied: {exc}")
            else:
                warnings.append(f"Function not applied: {function_name} is unavailable in this Sales Navigator view")

    for industry in plan.get("industries") or []:
        industry_name = str(industry).strip()
        if industry_name:
            await optional("Industry", _include_typeahead(
                page,
                filter_name="Industry",
                selected_filter_name="Industry",
                placeholder="Search industries",
                query=industry_name,
                expected_prefix=industry_name,
            ))

    geography = str(plan.get("geography") or "").strip()
    if geography:
        await optional("Geography", _include_typeahead(
            page,
            filter_name="Geography",
            selected_filter_name="Region",
            placeholder="Add locations",
            query=geography,
            expected_prefix=geography,
        ))

    session.manual_control = True
    return {
        "state": "manual_control",
        "current_url": page.url,
        "applied": applied,
        "warnings": warnings,
        "awaiting_auth": False,
    }


@app.post("/sessions/input", dependencies=[Depends(authorize)])
async def send_input(payload: SessionPayload) -> dict[str, Any]:
    session = _session(payload.session_id)
    allowed_keys = {"Backspace", "Delete", "Tab", "Enter", "Escape", "Control+A"}
    if bool(payload.text) == bool(payload.key):
        raise HTTPException(status_code=400, detail="Provide exactly one of text or key")
    if payload.text:
        await session.page.keyboard.insert_text(payload.text)
    elif payload.key in allowed_keys:
        await session.page.keyboard.press(payload.key)
    else:
        raise HTTPException(status_code=400, detail="Unsupported key")
    return {"state": "manual_control", "current_url": session.page.url}


@app.post("/sessions/lock", dependencies=[Depends(authorize)])
async def lock_search(payload: SessionPayload) -> dict[str, Any]:
    session = _session(payload.session_id)
    if "/sales/search/people" not in session.page.url:
        raise HTTPException(status_code=409, detail="Open a Sales Navigator people search before locking")
    session.manual_control = False
    return {"current_url": session.page.url}


@app.post("/sessions/take-control", dependencies=[Depends(authorize)])
async def take_control(payload: SessionPayload) -> dict[str, Any]:
    session = _session(payload.session_id)
    session.manual_control = True
    return {"state": "manual_control", "current_url": session.page.url}


@app.post("/sessions/release-control", dependencies=[Depends(authorize)])
async def release_control(payload: SessionPayload) -> dict[str, Any]:
    session = _session(payload.session_id)
    session.manual_control = False
    return {"state": "paused", "current_url": session.page.url}


@app.post("/sessions/extract/next", dependencies=[Depends(authorize)])
async def extract_next(payload: SessionPayload) -> dict[str, Any]:
    session = _session(payload.session_id)
    page = session.page
    if _auth_required(page.url):
        return {"auth_required": True, "current_url": page.url}
    if await _salesnav_rate_limited(page):
        return {"rate_limited": True, "current_url": page.url}
    if session.manual_control and not bool((payload.cursor or {}).get("automation")):
        raise HTTPException(status_code=409, detail="Release manual control before extraction")
    if "/sales/search/people" not in page.url:
        locked_search_url = str((payload.cursor or {}).get("locked_search_url") or "")
        if bool((payload.cursor or {}).get("automation")) and "/sales/search/people" in locked_search_url:
            await page.goto(locked_search_url, wait_until="domcontentloaded", timeout=60_000)
        else:
            raise HTTPException(status_code=409, detail="Browser is not on a Sales Navigator people search")
    search_url = page.url

    cursor = dict(payload.cursor or {})
    page_number = int(cursor.get("page", 1))
    max_pages = int(cursor.get("max_pages", 10))
    max_profiles = int(cursor.get("max_profiles", 200))
    extracted = int(cursor.get("extracted", 0))
    scraper = SalesNavScraper(li_at_cookie="", headless=False, max_pages=max_pages, max_profiles=max_profiles)

    # Fresh runs navigate to their locked URL immediately before this call.
    # Sales Navigator renders result cards asynchronously; without waiting we
    # mistook the initial empty DOM for a completed zero-result search.
    await scraper._wait_for_results(page)
    if await _salesnav_rate_limited(page):
        return {"rate_limited": True, "current_url": page.url}

    # Sales Navigator uses a virtual list: only the cards around the current
    # scroll position exist in the DOM.  A numeric DOM index therefore loses
    # the rest of a result page (the previous implementation stopped at 13 on
    # a 25-card page).  Keep stable lead URLs for the current page and advance
    # the actual results scroller whenever its visible window is exhausted.
    page_seen = set(str(value) for value in cursor.get("page_seen", []) if value)
    requested_scroll_top = int(cursor.get("scroll_top", 0))
    scroll_state = await page.evaluate(
        """scrollTop => {
          const container = document.querySelector('#search-results-container')
            || document.querySelector('[data-x--search-results-container]');
          if (!container) return { found: false, top: 0, height: 0, client: 0 };
          // Do not write `0` on the initial card.  Sales Navigator treats a
          // programmatic scroll event as a virtual-list refresh and can
          // invalidate the name-link click immediately afterwards.
          if (scrollTop > 0) container.scrollTop = Math.max(0, scrollTop);
          return {
            found: true,
            top: Math.round(container.scrollTop),
            height: Math.round(container.scrollHeight),
            client: Math.round(container.clientHeight),
          };
        }""",
        requested_scroll_top,
    )
    await page.wait_for_timeout(350)
    cards = await scraper._get_all_profile_cards(page)
    card = None
    card_key = ""
    card_lead_href = ""
    card_visible_index = 0
    for visible_index, visible_card in enumerate(cards):
        lead = await visible_card.query_selector('a[href*="/sales/lead/"]')
        card_key = (await lead.get_attribute("href")) if lead else ""
        if not card_key:
            card_key = " ".join((await visible_card.text_content() or "").split())[:400]
        if card_key and card_key not in page_seen:
            card = visible_card
            card_visible_index = visible_index
            card_lead_href = card_key
            break

    if card is None:
        # Move down by most of the viewport, preserving overlap so a lazy
        # render cannot skip a card at a list-window boundary.
        top = int(scroll_state.get("top") or 0)
        height = int(scroll_state.get("height") or 0)
        client = int(scroll_state.get("client") or 0)
        next_top = min(max(0, height - client), top + max(300, int(client * 0.7)))
        if scroll_state.get("found") and next_top > top + 2:
            next_cursor = {
                "page": page_number,
                "extracted": extracted,
                "max_pages": max_pages,
                "max_profiles": max_profiles,
                "fast": bool(cursor.get("fast")),
                "automation": bool(cursor.get("automation")),
                "locked_search_url": str(cursor.get("locked_search_url") or ""),
                "page_seen": list(page_seen),
                "scroll_top": next_top,
            }
            return {"current": extracted, "total": max_profiles, "cursor": next_cursor, "done": False}
        if page_number >= max_pages or not await scraper._has_next_page(page):
            return {"done": True, "current": extracted, "total": extracted, "cursor": cursor}
        await scraper._go_to_next_page(page)
        page_number += 1
        page_seen = set()
        await page.evaluate(
            """() => {
              const container = document.querySelector('#search-results-container')
                || document.querySelector('[data-x--search-results-container]');
              if (container) container.scrollTop = 0;
            }"""
        )
        scroll_state = {"top": 0, "height": 0, "client": 0}
        await page.wait_for_timeout(500)
        cards = await scraper._get_all_profile_cards(page)
        if not cards:
            return {"done": True, "current": extracted, "total": extracted, "cursor": cursor}
        card = cards[0]
        card_visible_index = 0
        lead = await card.query_selector('a[href*="/sales/lead/"]')
        card_key = (await lead.get_attribute("href")) if lead else ""
        if not card_key:
            card_key = " ".join((await card.text_content() or "").split())[:400]
        card_lead_href = card_key if card_key.startswith("/") else ""

    # Open the exact mounted result through Locator semantics.  ElementHandle
    # clicks are flaky in SalesNav's virtual list; this is same interaction
    # verified by drawer-debug against live Chromium.
    if not cursor.get("fast"):
        # Match the exact stable lead URL rather than a visible-card index.
        # The result list is virtualized: its DOM order can change between
        # discovery and click, which otherwise opens a different drawer.
        live_name_link = page.locator(
            f'a[data-control-name="view_lead_panel_via_search_lead_name"][href="{card_lead_href}"]'
        ) if card_lead_href else page.locator('a[data-control-name="view_lead_panel_via_search_lead_name"]').nth(card_visible_index)
        if await live_name_link.count():
            # Public-profile/contact dialogs can remain in modal outlet after
            # prior lead. Dismiss harmless overlay before next card.
            await page.keyboard.press("Escape")
            await live_name_link.scroll_into_view_if_needed()
            await live_name_link.click(timeout=8_000, force=True)
            try:
                await page.wait_for_selector(
                    'button[aria-label="Open actions overflow menu"]',
                    state="attached", timeout=8_000
                )
            except Exception:
                # SalesNav occasionally declines one drawer after a modal.
                # Preserve this result card and let later cards continue.
                pass

        drawer_text = ""
        drawer = page.locator("div.lead-sidesheet")
        if await drawer.count():
            drawer_text = await drawer.first.inner_text()
        if "trouble loading" in drawer_text.lower():
            # This is a Sales Navigator error panel, not an empty profile.
            # Refresh the locked search once and retry the same unmarked card.
            if cursor.get("drawer_recovery_attempted"):
                raise HTTPException(status_code=502, detail="Sales Navigator drawer still reports Trouble loading after refresh")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
            await scraper._wait_for_results(page)
            retry_cursor = {
                **cursor,
                "drawer_recovery_attempted": True,
                "page_seen": list(page_seen),
                "scroll_top": int(scroll_state.get("top") or 0),
            }
            return {"current": extracted, "total": max_profiles, "cursor": retry_cursor, "done": False}

    profile = (
        await scraper.parse_profile_card_fast(card, page)
        if cursor.get("fast")
        else await scraper._parse_profile_card(card, page)
    )
    if card_key:
        page_seen.add(card_key)
    if profile:
        extracted += 1
    # Public-profile actions may replace this tab in some SalesNav variants.
    # Every extract call must leave browser on same locked result search.
    if "/sales/search/people" not in page.url:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
        await scraper._wait_for_results(page)
    next_cursor = {
        "page": page_number,
        "extracted": extracted,
        "max_pages": max_pages,
        "max_profiles": max_profiles,
        "fast": bool(cursor.get("fast")),
        "automation": bool(cursor.get("automation")),
        "locked_search_url": str(cursor.get("locked_search_url") or ""),
        "page_seen": list(page_seen),
        "scroll_top": int(scroll_state.get("top") or 0),
    }
    done = extracted >= max_profiles
    return {
        "profile": profile,
        "current": extracted,
        "total": max_profiles,
        "cursor": next_cursor,
        "current_url": page.url,
        "done": done,
    }


@app.post("/sessions/profile", dependencies=[Depends(authorize)])
async def map_profile(payload: SessionPayload) -> dict[str, Any]:
    """Map public profile sections through authenticated persistent session."""
    session = _session(payload.session_id)
    if not payload.url or "linkedin.com/in/" not in payload.url:
        raise HTTPException(status_code=400, detail="LinkedIn profile URL required")
    page = await session.context.new_page()
    root = payload.url.split("?")[0].rstrip("/")
    sections = ["experience", "education", "skills", "languages", "certifications"]
    result: dict[str, Any] = {
        "linkedin_url": root,
        "source": "linkedin_local_profile",
        "sections": {},
        "section_items": {},
    }
    try:
        await page.goto(root, wait_until="domcontentloaded", timeout=60_000)
        if _auth_required(page.url):
            return {"auth_required": True, "current_url": page.url}
        if await _salesnav_rate_limited(page):
            return {"rate_limited": True, "current_url": page.url}
        await page.wait_for_timeout(1500)
        result.update(await page.evaluate(
            """() => {
              const text = (selector) => document.querySelector(selector)?.textContent?.trim() || '';
              const main = document.querySelector('main');
              const lines = (main?.innerText || '').split(String.fromCharCode(10)).map(v => v.trim()).filter(Boolean);
              const aboutHeading = [...(main?.querySelectorAll('h2') || [])].find(node =>
                /^(about|о себе|общие сведения)$/i.test((node.innerText || '').trim())
              );
              const aboutSection = aboutHeading?.closest('section');
              const aboutLines = (aboutSection?.innerText || '').split(String.fromCharCode(10))
                .map(v => v.trim()).filter(Boolean)
                .filter(v => !/^(about|о себе|общие сведения)$/i.test(v));
              const fullName = text('main h1') || text('main h2') || lines[0] || '';
              const headerLines = lines.slice(Math.max(0, lines.indexOf(fullName) + 1), 8)
                .filter(v => v !== '·' && !v.startsWith('·') && !/^(contact info|contact details|контактные сведения)$/i.test(v));
              return {
                full_name: fullName,
                headline: text('main .text-body-medium') || headerLines[0] || '',
                location: headerLines[1] || '',
                bio: aboutLines.join(' ').slice(0, 5000),
                raw_text: (main?.innerText || '').slice(0, 12000)
              };
            }"""
        ))
        for section in sections:
            url = f"{root}/details/{section}/"
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(1000)
            if await _salesnav_rate_limited(page):
                return {"rate_limited": True, "current_url": page.url}
            main = page.locator("main")
            result["sections"][section] = await main.inner_text(timeout=10_000)
            result["section_items"][section] = await main.evaluate(
                r"""main => [...main.querySelectorAll('li')]
                  .filter(item => !item.querySelector('li'))
                  .map(item => ({
                    lines: (item.innerText || '').split(String.fromCharCode(10))
                      .map(line => line.replace(/\s+/g, ' ').trim()).filter(Boolean),
                    links: [...item.querySelectorAll('a[href]')].map(link => ({
                      text: (link.innerText || link.textContent || '').trim(), href: link.href
                    })).filter(link => link.text),
                  }))
                  .filter(item => item.lines.length > 0)"""
            )
        return {"profile": result}
    finally:
        await page.close()


@app.post("/sessions/profile-header", dependencies=[Depends(authorize)])
async def map_profile_header(payload: SessionPayload) -> dict[str, Any]:
    """Read only the public profile header for fast location repair/resolution."""
    session = _session(payload.session_id)
    if not payload.url or "linkedin.com/in/" not in payload.url:
        raise HTTPException(status_code=400, detail="LinkedIn profile URL required")
    page = await session.context.new_page()
    try:
        root = payload.url.split("?")[0].rstrip("/")
        await page.goto(root, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(1200)
        if _auth_required(page.url):
            return {"auth_required": True, "current_url": page.url}
        if await _salesnav_rate_limited(page):
            return {"rate_limited": True, "current_url": page.url}
        profile = await page.evaluate(
            r"""() => {
              const main = document.querySelector('main');
              const lines = (main?.innerText || '').split(String.fromCharCode(10))
                .map(v => v.replace(/\s+/g, ' ').trim()).filter(Boolean);
              const fullName = document.querySelector('main h1')?.textContent?.trim()
                || document.querySelector('main h2')?.textContent?.trim() || lines[0] || '';
              const header = lines.slice(Math.max(0, lines.indexOf(fullName) + 1), 8)
                .filter(v => v !== '·' && !v.startsWith('·')
                  && !/^(contact info|contact details|контактные сведения)$/i.test(v));
              return {
                full_name: fullName,
                headline: document.querySelector('main .text-body-medium')?.textContent?.trim() || header[0] || '',
                location: header[1] || '',
                raw_text: lines.slice(0, 20).join(String.fromCharCode(10)),
              };
            }"""
        )
        return {"profile": profile, "current_url": page.url}
    finally:
        await page.close()


@app.post("/sessions/resolve-public-url", dependencies=[Depends(authorize)])
async def resolve_public_url(payload: SessionPayload) -> dict[str, Any]:
    """Resolve one SalesNav lead to its public profile via the read-only action menu."""
    session = _session(payload.session_id)
    if not payload.url or "linkedin.com/sales/lead/" not in payload.url:
        raise HTTPException(status_code=400, detail="Sales Navigator lead URL required")
    page = await session.context.new_page()
    try:
        await page.goto(payload.url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(1500)
        if _auth_required(page.url):
            return {"auth_required": True, "current_url": page.url}
        if await _salesnav_rate_limited(page):
            return {"rate_limited": True, "current_url": page.url}
        scraper = SalesNavScraper(li_at_cookie="", headless=False, max_profiles=1, max_pages=1)
        public_url = await scraper.sidebar_extractor.extract_profile_url_with_retry(page, 2)
        diagnostics = {}
        if "/in/" not in public_url:
            diagnostics = await page.evaluate(
                r"""() => ({
                  buttons: [...document.querySelectorAll('button')]
                    .filter(node => node.offsetParent !== null)
                    .map(node => ({
                      text: (node.innerText || '').replace(/\s+/g, ' ').trim(),
                      aria: node.getAttribute('aria-label') || '',
                      control: node.getAttribute('data-control-name') || '',
                    })).filter(item => item.text || item.aria).slice(0, 80),
                  publicLinks: [...document.querySelectorAll('a[href*="/in/"]')]
                    .map(node => node.href).slice(0, 20),
                })"""
            )
        return {
            "public_url": public_url if "/in/" in public_url else "",
            "current_url": page.url,
            "diagnostics": diagnostics,
        }
    finally:
        await page.close()


@app.post("/sessions/public-search", dependencies=[Depends(authorize)])
async def search_public_profiles(payload: SessionPayload) -> dict[str, Any]:
    """Search authenticated LinkedIn people results for public profile candidates."""
    session = _session(payload.session_id)
    query = " ".join(str(payload.text or "").split())
    if not query:
        raise HTTPException(status_code=400, detail="Profile search query required")
    page = await session.context.new_page()
    try:
        url = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(3000)
        if _auth_required(page.url):
            return {"auth_required": True, "current_url": page.url}
        if await _salesnav_rate_limited(page):
            return {"rate_limited": True, "current_url": page.url}
        candidates = await page.evaluate(
            r"""() => {
              const seen = new Set();
              return [...document.querySelectorAll('main a[href*="/in/"]')]
                .map(link => {
                  const href = (link.href || '').split('?')[0];
                  const container = link.closest('li') || link.closest('[data-view-name]') || link.parentElement;
                  return {href, text: (container?.innerText || link.innerText || '').replace(/\s+/g, ' ').trim()};
                })
                .filter(item => item.href && !seen.has(item.href) && seen.add(item.href))
                .slice(0, 20);
            }"""
        )
        return {"query": query, "candidates": candidates, "current_url": page.url}
    finally:
        await page.close()


@app.on_event("shutdown")
async def shutdown() -> None:
    for session in list(sessions.values()):
        await session.context.close()
        await session.playwright.stop()
    sessions.clear()
