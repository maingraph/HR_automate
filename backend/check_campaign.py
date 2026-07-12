import os
from app.core.db import get_supabase

def check_leads():
    sb = get_supabase()
    # Get latest campaign
    camp_r = sb.table("outreach_campaigns").select("*").order("created_at", desc=True).limit(1).execute()
    if not camp_r.data:
        print("No campaigns found")
        return
    campaign = camp_r.data[0]
    print(f"Latest Campaign ID: {campaign['id']}, Name: {campaign.get('name')}")
    print(f"tg_template: {bool(campaign.get('tg_template'))}, li_template: {bool(campaign.get('li_template'))}")
    
    # Get leads
    leads_r = sb.table("outreach_leads").select("*").eq("campaign_id", campaign["id"]).execute()
    leads = leads_r.data or []
    print(f"Found {len(leads)} leads")
    for l in leads:
        print(f"Lead ID: {l['id']}, Status: {l['status']}, PrefChannel: {l.get('preferred_channel')}, TG: {l.get('telegram_url')}, LI: {l.get('linkedin_url')}, Name: {l.get('full_name')}")

if __name__ == "__main__":
    check_leads()
