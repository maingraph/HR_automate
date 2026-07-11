import os
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

def debug_linkedin_click():
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
        
        print("Waiting for page to load...")
        page.wait_for_timeout(5000)
        
        print("Looking for Message button...")
        msg_button_selectors = [
            "a[href*='/messaging/compose/']",
            "button[aria-label^='Message']",
            "button:has-text('Message')",
            ".pvs-profile-actions button:has-text('Message')",
            "a:has-text('Message')",
            ".pvs-profile-actions a:has-text('Message')",
            ".pvs-profile-actions >> text='Message'"
        ]
        
        clicked = False
        for sel in msg_button_selectors:
            button = page.locator(sel).first
            if button.is_visible():
                href = button.get_attribute("href")
                if href and href.startswith("/"):
                    target_url = f"https://www.linkedin.com{href}"
                    print(f"Found href! Navigating directly to: {target_url}")
                    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    clicked = True
                    break
                else:
                    print(f"Clicking using JS: {sel}")
                    button.evaluate("node => node.click()")
                    clicked = True
                    break
        
        if not clicked:
            print("Failed to click Message button!")
        else:
            print("Clicked! Waiting 5s for overlay...")
            page.wait_for_timeout(5000)
        
        with open("debug_linkedin_overlay.html", "w") as f:
            f.write(page.content())
        print("HTML saved to debug_linkedin_overlay.html")

        screenshot_path = "debug_linkedin_overlay.png"
        try:
            page.screenshot(path=screenshot_path, timeout=5000)
            print(f"Screenshot saved to {screenshot_path}")
        except Exception as e:
            print(f"Screenshot failed: {e}")

        browser.close()

if __name__ == "__main__":
    debug_linkedin_click()
