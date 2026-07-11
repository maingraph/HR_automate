#!/usr/bin/env python3
"""Check migration status: verify orgs/users tables + org_id columns exist."""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.core.db import get_supabase

def check_migration():
    sb = get_supabase()

    print("=== Checking migration 006 status ===\n")

    # Check orgs table
    try:
        r = sb.table("orgs").select("id").limit(1).execute()
        print("✓ orgs table exists")
        print(f"  Rows: {len(r.data or [])}")
    except Exception as e:
        print(f"✗ orgs table missing: {e}")

    # Check users table
    try:
        r = sb.table("users").select("id").limit(1).execute()
        print("✓ users table exists")
        print(f"  Rows: {len(r.data or [])}")
    except Exception as e:
        print(f"✗ users table missing: {e}")

    # Check org_id on jobs
    try:
        r = sb.table("jobs").select("id,org_id").limit(1).execute()
        has_org_id = r.data and "org_id" in (r.data[0] if r.data else {})
        if has_org_id:
            print("✓ jobs.org_id exists")
        else:
            print("✗ jobs.org_id missing")
    except Exception as e:
        print(f"✗ jobs.org_id check failed: {e}")

    # Check org_id on candidates
    try:
        r = sb.table("candidates").select("id,org_id").limit(1).execute()
        has_org_id = r.data and "org_id" in (r.data[0] if r.data else {})
        if has_org_id:
            print("✓ candidates.org_id exists")
        else:
            print("✗ candidates.org_id missing")
    except Exception as e:
        print(f"✗ candidates.org_id check failed: {e}")

    # Check org_id on outreach_campaigns
    try:
        r = sb.table("outreach_campaigns").select("id,org_id").limit(1).execute()
        has_org_id = r.data and "org_id" in (r.data[0] if r.data else {})
        if has_org_id:
            print("✓ outreach_campaigns.org_id exists")
        else:
            print("✗ outreach_campaigns.org_id missing")
    except Exception as e:
        print(f"✗ outreach_campaigns.org_id check failed: {e}")

if __name__ == "__main__":
    check_migration()
