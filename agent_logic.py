import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def run_aurora_automation(rep_id, customer_name):
    print(f"LOG: Starting design workflow for {customer_name}")
    async with async_playwright() as p:
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--display=:99", 
                "--window-size=1280,1024"
            ]
        )
        page = await context.new_page()

        try:
            # --- 1. ROBUST NAVIGATION ---
            print(f"LOG: Navigating to projects (60s timeout)...")
            # Changed 'networkidle' to 'domcontentloaded' to avoid timeouts
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            
            # Wait for the search bar to confirm we are actually 'in'
            print("LOG: Waiting for search bar to appear...")
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.wait_for(state="visible", timeout=30000)

            # Dismiss popups
            try:
                await page.locator("button:has-text('Restore')").click(timeout=3000)
                print("LOG: Dismissed Chromium restore popup.")
            except: pass

            # --- 2. SEARCH & OPEN ---
            print(f"LOG: Searching for '{customer_name}'...")
            await search_input.click()
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)
            
            await page.locator(f"text='{customer_name}'").first.click()
            await asyncio.sleep(5)

            # --- 3. OPEN NEW DESIGN ---
            print("LOG: Clicking New Design...")
            # Using force=True because sometimes overlays block the button
            await page.get_by_role("button", name="New design").click(force=True)
            
            print("LOG: Waiting 40 seconds for CAD Engine...")
            await asyncio.sleep(40) 

            # --- 4. THE SIDEBAR CLICK LOOP ---
            print("LOG: Attempting to trigger AI SmartRoof...")
            
            # Ensure 'Site' tab is active
            await page.get_by_text("Site", exact=True).click(force=True)
            await asyncio.sleep(3)

            for attempt in range(3):
                print(f"LOG: Opening Roof Menu (Attempt {attempt+1})...")
                # Target the Roof list item
                await page.locator("li").filter(has_text="Roof").click(force=True)
                await asyncio.sleep(4)
                
                # Check if sub-menu is visible
                ai_button = page.get_by_text("AI SmartRoof")
                if await ai_button.is_visible():
                    print("LOG: AI SmartRoof button found! Clicking...")
                    await ai_button.click(force=True)
                    break
                else:
                    print("LOG: Sub-menu didn't open, retrying...")
                    # Click elsewhere to refresh focus
                    await page.mouse.click(500, 10) 
                    await asyncio.sleep(2)
            
            # --- 5. WAIT FOR MODELING ---
            print("LOG: Waiting for 'AI SmartRoof complete' status...")
            await page.wait_for_selector("text=AI SmartRoof complete", timeout=120000)
            print("LOG: AI Modeling finished.")

            # --- 6. SYSTEM -> AUTODESIGNER ---
            print("LOG: Navigating to System menu...")
            await page.get_by_text("System", exact=True).click(force=True)
            await asyncio.sleep(3)
            
            await page.get_by_text("AutoDesigner").click(force=True)
            await asyncio.sleep(2)
            await page.get_by_role("button", name="Run AutoDesigner").click(force=True)

            # --- 7. HANDLE INVERTER ERROR ---
            print("LOG: Monitoring for Inverter Error...")
            await asyncio.sleep(10)
            
            if await page.get_by_text("Inverter is required").is_visible():
                print("LOG: Fixing Inverter Error...")
                await page.get_by_text("Site", exact=True).click(force=True)
                await page.get_by_text("Components").click(force=True)
                await page.get_by_text("Select Inverter").click(force=True)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                await asyncio.sleep(3)
                
                await page.get_by_text("System", exact=True).click(force=True)
                await page.get_by_text("AutoDesigner").click(force=True)
                await page.get_by_role("button", name="Run AutoDesigner").click(force=True)
                await page.wait_for_selector("text=AutoDesigner completed", timeout=60000)

            # --- 8. FINISH & SALES MODE ---
            print("LOG: Entering Sales Mode...")
            await page.get_by_text("Sales mode").click(force=True)
            
            await asyncio.sleep(20) # Extra time for proposal to generate
            final_url = page.url
            print(f"LOG: SUCCESS! Final URL: {final_url}")
            
            return final_url

        except Exception as e:
            print(f"!!! WORKFLOW ERROR: {e}")
            await page.screenshot(path="cad_error.png")
            return f"ERROR: {str(e)}"

        finally:
            print("LOG: Keeping browser open for 5 mins for review.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))