"""Apply supabase/schema.sql using service_role key via HTTP SQL endpoint."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "backend"))

import httpx
from app.core.config import settings

SQL_FILE = pathlib.Path(__file__).parents[1] / "supabase" / "schema.sql"
sql = SQL_FILE.read_text()

# Supabase exposes a direct SQL endpoint for service_role
url = f"{settings.supabase_url}/rest/v1/rpc/exec_sql"
headers = {
    "apikey": settings.supabase_service_role_key,
    "Authorization": f"Bearer {settings.supabase_service_role_key}",
    "Content-Type": "application/json",
}

# Try using pg_meta endpoint (available on self-hosted) or raw SQL via db endpoint
# For hosted Supabase the cleanest path is the /pg endpoint
pg_url = f"{settings.supabase_url.replace('https://', 'https://').rstrip('/')}"

# Use the Supabase SQL API via postgrest and admin endpoint
sql_api = settings.supabase_url.replace("https://", "https://").rstrip("/")
# Supabase hosted exposes direct SQL at: https://<ref>.supabase.co/rest/v1/
# We split the SQL into DDL statements and execute via the admin REST

# Actually, use the pg admin API available with service_role
r = httpx.post(
    f"{sql_api}/rest/v1/",
    headers={**headers, "Prefer": "return=representation"},
    content=sql,
    params={"_type": "query"},
    timeout=60,
)
print("status:", r.status_code, r.text[:300])
