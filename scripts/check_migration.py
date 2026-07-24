#!/usr/bin/env python3
"""Verify required Sourcer tables and columns exist."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.db import get_supabase


REQUIRED_SCHEMA = {
    "orgs": "id",
    "users": "id,org_id",
    "jobs": "id,org_id",
    "candidates": "id,org_id",
    "outreach_campaigns": "id,org_id",
    "candidate_datasets": "id,org_id,state,capabilities",
    "candidate_records": "id,org_id,dataset_id,candidate_key",
    "stage_runs": "id,org_id,job_id,stage_type,status",
    "browser_sessions": "id,org_id,job_id,state",
}


def check_migration() -> bool:
    client = get_supabase()
    failures: list[str] = []

    print("=== Sourcer schema readiness ===")
    for table, columns in REQUIRED_SCHEMA.items():
        try:
            client.table(table).select(columns).limit(1).execute()
            print(f"✓ {table}: {columns}")
        except Exception as exc:
            failures.append(table)
            print(f"✗ {table}: {type(exc).__name__}: {exc}")

    if failures:
        print(f"\nSchema incomplete: {', '.join(failures)}")
        return False
    print("\nSchema ready.")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if check_migration() else 1)
