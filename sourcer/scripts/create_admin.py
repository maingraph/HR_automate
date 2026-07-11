#!/usr/bin/env python3
"""Create admin user for Sourcer platform."""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.auth import hash_password
from app.core.db import get_supabase

def create_admin(email: str, password: str):
    """Create platform admin user attached to Default Org."""
    sb = get_supabase()

    # Get Default Org
    org_r = sb.table("orgs").select("id").eq("id", "00000000-0000-0000-0000-000000000001").single().execute()
    if not org_r.data:
        print("ERROR: Default Org not found. Run migration 006 first.")
        sys.exit(1)

    org_id = org_r.data["id"]

    # Check if user exists
    existing = sb.table("users").select("id").eq("email", email).execute()
    if existing.data:
        print(f"User {email} already exists.")
        sys.exit(1)

    # Create admin user
    user_row = {
        "org_id": org_id,
        "email": email,
        "password_hash": hash_password(password),
        "role": "platform_admin",
    }

    result = sb.table("users").insert(user_row).execute()
    if result.data:
        print(f"✓ Created platform_admin user: {email}")
        print(f"  Org: Default Org ({org_id})")
    else:
        print("ERROR: Failed to create user")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_admin.py <email> <password>")
        sys.exit(1)

    create_admin(sys.argv[1], sys.argv[2])
