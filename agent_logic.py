import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def run_aurora_automation(rep_id, customer_name):
    async with async_playwright() as p:
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--display=:99", "--window-size=1280,1024"]
        )
        page = await context.new_page()

        print(f"LOG: Navigating to Projects page...")
        await page.goto("https://v2.aurorasolar.com/projects", wait_until="networkidle")
        await asyncio.sleep(5)

        # 1. SEARCH FOR CUSTOMER
        print(f"LOG: Looking for search bar...")
        try:
            # Aurora V2 search bar usually has a simple 'Search' placeholder or is the first input
            search_box = page.locator("input[placeholder*='Search']").first
            await search_box.wait_for(state="visible", timeout=10000)
            await search_box.click()
            await search_box.fill(customer_name)
            await page.keyboard.press("Enter")
            print(f"LOG: Typed '{customer_name}' into search.")
        except Exception as e:
            print("LOG: Could not find search box by placeholder. Trying generic input...")
            await page.locator("input").first.fill(customer_name)
            await page.keyboard.press("Enter")

        # Wait for results to filter
        await asyncio.sleep(5) 

        # 2. CLICK ON CUSTOMER
        print(f"LOG: Attempting to click customer in the table...")
        try:
            # We look for the text of the customer name inside the table
            # In your screenshot, it's 'Test Testcase - LGCY Design'
            # We use 'has-text' to be flexible
            customer_selector = page.get_by_text(customer_name, exact=False).first
            await customer_selector.wait_for(state="visible", timeout=10000)
            
            # Highlight the element for a second so you can see it in VNC
            await customer_selector.evaluate("el => el.style.border = '5px solid red'")
            await asyncio.sleep(2)
            
            await customer_selector.click()
            print("LOG: Successfully clicked customer.")
        except Exception as e:
            print(f"ERROR: Failed to click customer. Taking error screenshot.")
            await page.screenshot(path="error_click.png")

        # 3. KEEP VNC ALIVE FOR DEBUGGING
        print("LOG: Logic complete. Keeping browser open for 5 minutes for you to inspect...")
        # This prevents the black screen
        await asyncio.sleep(300) 
        
        # await context.close() # Commented out to prevent black screen
        return "SUCCESS"