import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def run_aurora_automation(rep_id, customer_name):
    print(f"\n--- DEBUG START: rep_id={rep_id}, customer={customer_name} ---")
    
    # 1. Setup Browser
    async with async_playwright() as p:
        try:
            profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
            
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=False,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--display=:99", "--window-size=1280,1024"]
            )
            page = await context.new_page()

            # 2. Go to Projects
            print("STEP 1: Navigating...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="networkidle", timeout=60000)
            
            # 3. Search (The likely crash point)
            print("STEP 2: Searching...")
            # We use a very generic selector to avoid crashes
            search_input = page.locator("input").first 
            await search_input.wait_for(state="visible", timeout=20000)
            await search_input.click()
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            
            print(f"STEP 3: Wait for results for {customer_name}...")
            await asyncio.sleep(5)

            # 4. Click Customer
            print("STEP 4: Clicking...")
            # Use a more aggressive selector
            customer_link = page.get_by_text(customer_name, exact=False).first
            await customer_link.click(timeout=10000)
            print("STEP 5: Success! Customer page should be open.")

        except Exception as e:
            print(f"!!! CRASH DETECTED: {e}")
            # Even if it crashes, take a screenshot of the error
            try:
                await page.screenshot(path="crash_debug.png")
                print("Screenshot 'crash_debug.png' saved.")
            except:
                pass

        # 5. THE STAY-ALIVE COMMAND
        print("FORCE SLEEP: Keeping browser open for 10 minutes for inspection. DO NOT CLOSE.")
        await asyncio.sleep(600) 
        return "FINISHED"

# This part allows you to run 'python3 agent_logic.py' directly
if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))