import os
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

def debug_linkedin():
    print("Starting Playwright debug...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        
        li_at = os.environ.get("LINKEDIN_LI_AT")
        if not li_at:
            print("No LINKEDIN_LI_AT cookie found.")
            return

        context.add_cookies([{
            "name": "li_at",
            "value": li_at,
            "domain": ".linkedin.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
        }])
        
        page = context.new_page()
        url = "https://www.linkedin.com/in/artem-naumchik-a3079a328/"
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        print("Waiting for 5 seconds...")
        page.wait_for_timeout(5000)
        
        screenshot_path = "debug_linkedin.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        
        # Also grab the HTML
        with open("debug_linkedin.html", "w") as f:
            f.write(page.content())
        print("HTML saved to debug_linkedin.html")

        browser.close()

if __name__ == "__main__":
    debug_linkedin()
