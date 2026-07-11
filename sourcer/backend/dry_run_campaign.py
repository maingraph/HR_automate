"""Simulate send_campaign_batch against the latest campaign without actually sending."""
from app.core.db import get_supabase

sb = get_supabase()

camp_r = sb.table("outreach_campaigns").select("*").order("created_at", desc=True).limit(1).execute()
campaign = camp_r.data[0]
print(f"Campaign: {campaign['id']} — {campaign.get('name')}, status: {campaign.get('status')}")
print(f"tg_template: {'✅' if campaign.get('tg_template') else '❌'}")
print(f"li_template: {'✅' if campaign.get('li_template') else '❌'}")

leads_r = sb.table("outreach_leads").select("*").eq("campaign_id", campaign["id"]).eq("status", "pending").execute()
leads = leads_r.data or []
print(f"\nPending leads: {len(leads)}")

for lead in leads:
    channel = lead.get("preferred_channel") or "telegram"
    template = campaign.get("tg_template") if channel == "telegram" else campaign.get("li_template")
    has_url = lead.get("telegram_url") if channel == "telegram" else lead.get("linkedin_url")
    
    print(f"\n  Lead: {lead.get('full_name')}")
    print(f"    channel: {channel}")
    print(f"    url: {has_url}")
    print(f"    template: {'✅' if template else '❌ MISSING — will skip!'}")
    print(f"    → would {'SEND' if template and has_url else 'SKIP'}")
