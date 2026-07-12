"""Persistent Chromium controller displayed through local noVNC."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        executable_path=EXECUTABLE if Path(EXECUTABLE).exists() else None,
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        timezone_id="Europe/Warsaw",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-password-manager-reauthentication",
            "--password-store=basic",
            "--no-first-run",
        ],
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    sessions[payload.session_id] = ManagedSession(payload.session_id, playwright, context, page)
    return {"state": "ready", "current_url": page.url}


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
    if session.manual_control:
        raise HTTPException(status_code=409, detail="Release manual control before extraction")
    if "/sales/search/people" not in page.url:
        raise HTTPException(status_code=409, detail="Browser is not on a Sales Navigator people search")

    cursor = dict(payload.cursor or {})
    page_number = int(cursor.get("page", 1))
    card_index = int(cursor.get("card_index", 0))
    max_pages = int(cursor.get("max_pages", 10))
    max_profiles = int(cursor.get("max_profiles", 200))
    extracted = int(cursor.get("extracted", 0))
    scraper = SalesNavScraper(li_at_cookie="", headless=False, max_pages=max_pages, max_profiles=max_profiles)

    await scraper._scroll_to_load_all(page)
    cards = await scraper._get_all_profile_cards(page)
    if card_index >= len(cards):
        if page_number >= max_pages or not await scraper._has_next_page(page):
            return {"done": True, "current": extracted, "total": extracted, "cursor": cursor}
        await scraper._go_to_next_page(page)
        page_number += 1
        card_index = 0
        cards = await scraper._get_all_profile_cards(page)
        if not cards:
            return {"done": True, "current": extracted, "total": extracted, "cursor": cursor}

    profile = await scraper._parse_profile_card(cards[card_index], page)
    card_index += 1
    if profile:
        extracted += 1
    next_cursor = {
        "page": page_number,
        "card_index": card_index,
        "extracted": extracted,
        "max_pages": max_pages,
        "max_profiles": max_profiles,
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
    sections = ["experience", "education", "skills", "languages"]
    result: dict[str, Any] = {
        "linkedin_url": root,
        "source": "linkedin_local_profile",
        "sections": {},
    }
    try:
        await page.goto(root, wait_until="domcontentloaded", timeout=60_000)
        if _auth_required(page.url):
            return {"auth_required": True, "current_url": page.url}
        await page.wait_for_timeout(1500)
        result.update(await page.evaluate(
            """() => {
              const text = (selector) => document.querySelector(selector)?.textContent?.trim() || '';
              const main = document.querySelector('main');
              const lines = (main?.innerText || '').split('\n').map(v => v.trim()).filter(Boolean);
              return {
                full_name: text('main h1') || text('main h2') || lines[0] || '',
                headline: text('main .text-body-medium') || lines[1] || '',
                raw_text: (main?.innerText || '').slice(0, 12000)
              };
            }"""
        ))
        for section in sections:
            url = f"{root}/details/{section}/"
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(1000)
            result["sections"][section] = await page.locator("main").inner_text(timeout=10_000)
        result["bio"] = "\n\n".join(
            text[:8000] for text in result["sections"].values() if text
        )[:20000]
        result["positions"] = [{"raw_text": result["sections"].get("experience", "")[:8000]}]
        result["educations"] = [{"raw_text": result["sections"].get("education", "")[:8000]}]
        result["skills"] = [
            line.strip() for line in result["sections"].get("skills", "").splitlines()
            if line.strip() and len(line.strip()) < 100
        ][:100]
        result["languages"] = [
            line.strip() for line in result["sections"].get("languages", "").splitlines()
            if line.strip() and len(line.strip()) < 100
        ][:50]
        return {"profile": result}
    finally:
        await page.close()


@app.on_event("shutdown")
async def shutdown() -> None:
    for session in list(sessions.values()):
        await session.context.close()
        await session.playwright.stop()
    sessions.clear()
