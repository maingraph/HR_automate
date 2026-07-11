"""Detect the local Chrome profile that's currently logged into LinkedIn.

Mirrors ``linkedin-sales-nav-parser/src/utils/chrome-detector.ts`` —
we probe ``~/Library/Application Support/Google/Chrome/{Default,Profile N}``
for either a ``Cookies`` sqlite file (legitimate profile) or ``Network/``
directory (Chromium variant), and return the first match.

LinkedIn ties its session cookie to the user's Chrome profile, so by
launching a persistent context against the same directory we inherit the
authenticated session without needing the cookie value or the password.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import List, Optional


CHROME_ROOT = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
CHROME_BIN_DEFAULT = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _candidate_dirs() -> List[Path]:
    if not CHROME_ROOT.exists():
        return []
    names = ["Default"] + [f"Profile {i}" for i in range(1, 11)]
    out: List[Path] = []
    for n in names:
        p = CHROME_ROOT / n
        if p.exists():
            out.append(p)
    return out


def _has_cookies(db_path: Path) -> bool:
    """Return True if the Cookies sqlite has at least one row."""
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro&uri=true", timeout=2) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM cookies")
            return cur.fetchone()[0] > 0
    except Exception:
        return False


def profile_has_linkedin_session(profile_dir: Path) -> bool:
    """Heuristic: cookies.sqlite exists and contains a `li_at` host entry.

    Fallback to non-empty cookies table if the column read fails for any
    reason (file may be locked by Chrome while it's running — in which
    case the persistent-context launch still works if Chrome is closed).
    """
    cookies_path = profile_dir / "Cookies"
    if cookies_path.exists():
        try:
            with sqlite3.connect(f"file:{cookies_path}?mode=ro&uri=true", timeout=2) as conn:
                row = conn.execute(
                    "SELECT 1 FROM cookies WHERE host_key LIKE '%linkedin.com%' LIMIT 1"
                ).fetchone()
                return row is not None
        except Exception:
            return _has_cookies(cookies_path)
    network_dir = profile_dir / "Network"
    return network_dir.exists()


def detect_chrome_profile() -> Path:
    """Return the first Chrome profile directory that looks logged-in."""
    candidates = _candidate_dirs()
    for p in candidates:
        if profile_has_linkedin_session(p):
            return p
    raise RuntimeError(
        "Could not find a Chrome profile with an active LinkedIn session.\n"
        "Open Chrome, sign in to linkedin.com, then re-run this tool."
    )


def list_candidate_profiles() -> List[Path]:
    return _candidate_dirs()


def get_chrome_executable_path() -> str:
    if os.path.exists(CHROME_BIN_DEFAULT):
        return CHROME_BIN_DEFAULT
    raise RuntimeError(
        f"Google Chrome not found at {CHROME_BIN_DEFAULT}. "
        "Install Chrome or set the CHROME_PATH environment variable."
    )
