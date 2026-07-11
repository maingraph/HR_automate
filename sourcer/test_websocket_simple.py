"""
Simple WebSocket test - just check connection and notifications.

Usage:
    python test_websocket_simple.py
"""
import asyncio
from playwright.async_api import async_playwright
import sys

async def test_websocket():
    """Test WebSocket connection on existing job page."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Track WebSocket
        ws_messages = []
        console_logs = []
        
        def on_ws(ws):
            ws.on("framereceived", lambda payload: ws_messages.append(payload))
        
        page.on("websocket", on_ws)
        page.on("console", lambda msg: console_logs.append(msg.text))
        
        print("✓ Browser launched")
        
        # Go to home and find/create job
        await page.goto("http://localhost:3000")
        await page.wait_for_load_state("networkidle")
        print("✓ Home page loaded")
        
        # Check if there are existing jobs
        job_links = await page.query_selector_all('a[href^="/jobs/"]')
        
        if job_links:
            # Click first job
            await job_links[0].click()
            await page.wait_for_url("**/jobs/**")
            print("✓ Opened existing job")
        else:
            print("⚠️  No existing jobs found")
            print("   Please create a job manually in the browser")
            print("   Test will wait 60s...")
            await page.wait_for_timeout(60000)
            return
        
        job_id = page.url.split("/")[-1]
        print(f"✓ Job ID: {job_id}")
        
        # Wait for WebSocket
        await page.wait_for_timeout(3000)
        
        # Check console
        ws_connected = any("WebSocket connected" in log for log in console_logs)
        ws_room = any("room joined" in log for log in console_logs)
        ws_errors = [log for log in console_logs if "WebSocket error" in log or "failed" in log.lower()]
        
        print(f"\n{'='*60}")
        print("WebSocket Status")
        print(f"{'='*60}")
        print(f"Connected: {'✓' if ws_connected else '✗'}")
        print(f"Room joined: {'✓' if ws_room else '✗'}")
        print(f"Messages received: {len(ws_messages)}")
        print(f"Errors: {len(ws_errors)}")
        
        if ws_errors:
            print("\nErrors:")
            for err in ws_errors[:3]:
                print(f"  {err}")
        
        # Check backend logs
        print(f"\n{'='*60}")
        print("Check Terminal 2 (FastAPI) for:")
        print(f"{'='*60}")
        print("  - 'WebSocket connected to room'")
        print("  - No 'Need to call accept first' errors")
        
        print("\nBrowser stays open 20s for inspection...")
        await page.wait_for_timeout(20000)
        
        await browser.close()
        
        # Result
        if ws_connected and ws_room and not ws_errors:
            print("\n✓ WebSocket test PASSED")
            return 0
        else:
            print("\n✗ WebSocket test FAILED")
            return 1

if __name__ == "__main__":
    try:
        result = asyncio.run(test_websocket())
        sys.exit(result or 0)
    except KeyboardInterrupt:
        print("\n✗ Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
