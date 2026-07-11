"""
Playwright test script for Phase 3 WebSocket functionality.

Tests:
1. WebSocket connection
2. Real-time job updates
3. Pipeline progress streaming

Usage:
    python test_websocket_ui.py
"""
import asyncio
from playwright.async_api import async_playwright, expect
import sys

async def test_websocket_flow():
    """Test WebSocket real-time updates through UI."""
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Track WebSocket connections
        ws_connections = []
        page.on("websocket", lambda ws: ws_connections.append(ws))
        
        # Track console logs
        console_logs = []
        page.on("console", lambda msg: console_logs.append(msg.text))
        
        print("✓ Browser launched")
        
        # Step 1: Navigate to home
        await page.goto("http://localhost:3000")
        await page.wait_for_load_state("networkidle")
        print("✓ Home page loaded")
        
        # Step 2: Create job
        await page.fill('input[name="title"]', 'Test CTO')
        await page.fill('textarea[name="tg_channels"]', 'https://t.me/hr_breakfast')
        print("✓ Job form filled")
        
        # Step 3: Navigate to sources
        await page.click('text=Sources')
        await page.wait_for_timeout(500)
        print("✓ Sources step")
        
        # Step 4: Launch job
        await page.click('text=Launch')
        await page.wait_for_timeout(1000)
        
        # Wait for job page
        await page.wait_for_url("**/jobs/**", timeout=10000)
        job_url = page.url
        job_id = job_url.split("/")[-1]
        print(f"✓ Job created: {job_id}")
        
        # Step 5: Check WebSocket connection
        await page.wait_for_timeout(2000)
        
        ws_connected = any("WebSocket connected" in log for log in console_logs)
        ws_room_joined = any("WebSocket room joined" in log for log in console_logs)
        
        print(f"\n{'='*60}")
        print("WebSocket Test Results")
        print(f"{'='*60}")
        print(f"WebSocket connections: {len(ws_connections)}")
        print(f"Console logs: {len(console_logs)}")
        print(f"WebSocket connected: {ws_connected}")
        print(f"WebSocket room joined: {ws_room_joined}")
        
        # Check for errors
        errors = [log for log in console_logs if "error" in log.lower() or "failed" in log.lower()]
        if errors:
            print(f"\n⚠️  Errors found:")
            for err in errors[:5]:
                print(f"  - {err}")
        
        # Step 6: Trigger pipeline
        print(f"\n{'='*60}")
        print("Triggering pipeline...")
        print(f"{'='*60}")
        
        await page.click('text=Launch sourcing agent')
        await page.wait_for_timeout(3000)
        
        # Check for status updates
        status_element = await page.query_selector('text=/Queued|Running|Phase 1/')
        if status_element:
            status_text = await status_element.text_content()
            print(f"✓ Status updated: {status_text}")
        else:
            print("✗ No status update detected")
        
        # Check Network tab for polling
        print(f"\n{'='*60}")
        print("Checking for polling requests...")
        print(f"{'='*60}")
        
        # Wait and monitor requests
        requests = []
        page.on("request", lambda req: requests.append(req.url))
        await page.wait_for_timeout(5000)
        
        job_requests = [r for r in requests if f"/jobs/{job_id}" in r and "/ws/" not in r]
        print(f"Job API requests in 5s: {len(job_requests)}")
        
        if len(job_requests) > 3:
            print("⚠️  Polling detected (should use WebSocket)")
        else:
            print("✓ Minimal polling (WebSocket working)")
        
        # Final summary
        print(f"\n{'='*60}")
        print("Test Summary")
        print(f"{'='*60}")
        print(f"✓ Job created: {job_id}")
        print(f"{'✓' if ws_connected else '✗'} WebSocket connected")
        print(f"{'✓' if ws_room_joined else '✗'} WebSocket room joined")
        print(f"{'✓' if len(job_requests) <= 3 else '⚠️'} Polling minimized")
        print(f"{'✓' if not errors else '⚠️'} No critical errors")
        
        # Keep browser open for inspection
        print("\nBrowser will stay open for 30s for inspection...")
        await page.wait_for_timeout(30000)
        
        await browser.close()
        print("\n✓ Test complete")

if __name__ == "__main__":
    try:
        asyncio.run(test_websocket_flow())
    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
