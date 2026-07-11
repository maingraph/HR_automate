"""Patch the latest campaign to set an li_template so existing leads can be re-run."""
from app.core.db import get_supabase
from datetime import datetime, timezone

sb = get_supabase()

# Get latest campaign
camp_r = sb.table("outreach_campaigns").select("*").order("created_at", desc=True).limit(1).execute()
if not camp_r.data:
    print("No campaigns found")
    exit(1)
campaign = camp_r.data[0]
print(f"Campaign: {campaign['id']} — {campaign.get('name')}")
print(f"Current li_template: {campaign.get('li_template')}")

li_template = """Hi {name},

I came across your LinkedIn profile and wanted to reach out — we're looking for a strong FB Media Buyer for a team working across Tier-1/2/3 GEOs in iGaming.

Key details:
• CPA model, budgets from $70K+
• Full infrastructure provided
• Fix + bonus grid, real growth to Team Lead

Would love to chat if you're open to it!"""

sb.table("outreach_campaigns").update({
    "li_template": li_template,
    "updated_at": datetime.now(tz=timezone.utc).isoformat()
}).eq("id", campaign["id"]).execute()

# Reset skipped leads to pending so they can be re-sent
leads_r = sb.table("outreach_leads").select("id, status").eq("campaign_id", campaign["id"]).eq("status", "skipped").execute()
skipped = leads_r.data or []
print(f"Resetting {len(skipped)} skipped leads to pending...")
for lead in skipped:
    sb.table("outreach_leads").update({
        "status": "pending",
        "updated_at": datetime.now(tz=timezone.utc).isoformat()
    }).eq("id", lead["id"]).execute()

# Reset campaign to draft so it can be started again
sb.table("outreach_campaigns").update({
    "status": "draft",
    "updated_at": datetime.now(tz=timezone.utc).isoformat()
}).eq("id", campaign["id"]).execute()

print("Done! li_template set, leads reset to pending, campaign reset to draft.")
print("You can now click 'Start campaign' again.")
