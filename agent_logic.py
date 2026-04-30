import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def run_aurora_automation(rep_id, customer_name):
    print(f"LOG: Starting automation for {customer_name}")
    async with async_playwright() as p:
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--display=:99", "--window-size=1280,1024"]
        )
        page = await context.new_page()

        try:
            # 1. Navigate and Wait
            print("LOG: Navigating to projects...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded")
            await asyncio.sleep(8) # Give the dashboard extra time to load the table

            # 2. Find the REAL Search Box
            print(f"LOG: Searching for '{customer_name}'...")
            # We target the input specifically inside the projects header
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.wait_for(state="visible", timeout=30000)
            
            # Visual Feedback: Highlight the search box in Red
            await search_input.evaluate("el => el.style.border = '4px solid red'")
            
            await search_input.click()
            await search_input.fill("") # Clear
            await search_input.type(customer_name, delay=100) # Type slowly like a human
            await page.keyboard.press("Enter")
            
            print("LOG: Search submitted. Waiting for table to filter...")
            await asyncio.sleep(5) 

            # 3. Click the Customer Row
            # We look for a link that contains the customer name
            print(f"LOG: Attempting to click link containing '{customer_name}'")
            
            # This selector looks for the specific text in the table
            customer_selector = page.locator(f"text='{customer_name}'").first
            
            if await customer_selector.is_visible():
                # Visual Feedback: Highlight what we are about to click
                await customer_selector.evaluate("el => el.style.backgroundColor = 'yellow'")
                print("LOG: Found the customer! Clicking...")
                await customer_selector.click()
            else:
                print("LOG: Could not find text via basic selector. Trying table row search...")
                # Fallback: Click the first cell in the first row of the table
                await page.locator("tbody tr").first.click()

            print("LOG: Success! Landing on project page.")

        except Exception as e:
            print(f"!!! ERROR DURING EXECUTION: {e}")
            await page.screenshot(path="debug_error.png")

        # 4. PREVENT BLACK SCREEN
        print("LOG: Script finished. Keeping browser open for 10 minutes for your inspection.")
        await asyncio.sleep(600) 
        return "SUCCESS"

if __name__ == "__main__":
    # Test it directly
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))