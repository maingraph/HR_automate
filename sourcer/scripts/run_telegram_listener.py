#!/usr/bin/env python
"""Start the persistent Telegram reply listener.

Usage:
    cd backend
    python ../scripts/run_telegram_listener.py

Or via launch.sh (started automatically alongside the API + Celery worker).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.outreach.telegram_listener import main  # noqa: E402

if __name__ == "__main__":
    main()
