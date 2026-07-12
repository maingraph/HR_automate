import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_URL = "http://localhost:8000"

def run_test():
    print("🚀 Starting Outreach Integration Test...")

    # 1. Create a Test Campaign
    campaign_payload = {
        "name": "System Integration Test",
        "tg_template": "Hello {full_name}, this is a test message from the Sourcer Telegram integration! 🚀",
        "li_template": "Hi {full_name}, I'm testing the Sourcer LinkedIn automation. Hope you're having a great day!",
    }
    
    resp = requests.post(f"{API_URL}/outreach/campaigns", json=campaign_payload)
    if resp.status_code != 200:
        print(f"❌ Failed to create campaign: {resp.text}")
        return
    
    campaign = resp.data if hasattr(resp, 'data') else resp.json()
    campaign_id = campaign['id']
    print(f"✅ Created Test Campaign: {campaign_id}")

    # 2. Add Telegram Lead
    tg_lead_payload = {
        "campaign_id": campaign_id,
        "full_name": "Test User (Telegram)",
        "telegram_url": "@shoksin6",
        "preferred_channel": "telegram",
        "source": "manual_test",
        "status": "pending"
    }
    
    # We need to use the DB directly or find an endpoint to add a single lead.
    # Looking at routes_outreach.py, there isn't a POST /leads endpoint, only import-xlsx.
    # I'll use the Supabase client directly to insert leads.
    from supabase import create_client
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    sb = create_client(url, key)
    
    tg_res = sb.table("outreach_leads").insert(tg_lead_payload).execute()
    tg_lead_id = tg_res.data[0]['id']
    print(f"✅ Added Telegram Lead: {tg_lead_id}")

    # 3. Add LinkedIn Lead
    li_lead_payload = {
        "campaign_id": campaign_id,
        "full_name": "Test User (LinkedIn)",
        "linkedin_url": "https://www.linkedin.com/in/artem-naumchik-a3079a328/",
        "preferred_channel": "linkedin",
        "source": "manual_test",
        "status": "pending"
    }
    li_res = sb.table("outreach_leads").insert(li_lead_payload).execute()
    li_lead_id = li_res.data[0]['id']
    print(f"✅ Added LinkedIn Lead: {li_lead_id}")

    # 4. Trigger Telegram Send
    print("📤 Sending Telegram message...")
    tg_send_resp = requests.post(f"{API_URL}/outreach/leads/{tg_lead_id}/send", json={"channel": "telegram"})
    print(f"Telegram Result: {tg_send_resp.json()}")

    # 5. Trigger LinkedIn Send
    print("📤 Sending LinkedIn message (this will take a moment for Playwright)...")
    li_send_resp = requests.post(f"{API_URL}/outreach/leads/{li_lead_id}/send", json={"channel": "linkedin"})
    print(f"LinkedIn Result: {li_send_resp.json()}")

    print("\n🎉 Test Finished!")

if __name__ == "__main__":
    run_test()
