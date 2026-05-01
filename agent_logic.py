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
                "--window-size=1280,1024",
                "--start-maximized"
            ]
        )
        page = await context.new_page()

        try:
            # --- 1. NAVIGATION & PROJECT OPENING ---
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="networkidle")
            await asyncio.sleep(5)
            
            # Dismiss any 'Restore' or 'Crash' popups immediately
            try:
                await page.locator("button:has-text('Restore')").click(timeout=3000)
                print("LOG: Dismissed Chromium restore popup.")
            except: pass

            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)
            
            # Click the customer project link
            await page.locator(f"text='{customer_name}'").first.click()
            await asyncio.sleep(5)

            # --- 2. OPEN NEW DESIGN ---
            print("LOG: Clicking New Design...")
            await page.get_by_role("button", name="New design").click()
            
            # Wait for CAD Engine (The 'Coming right up' screen)
            print("LOG: Waiting for 3D CAD Engine (35 seconds)...")
            await asyncio.sleep(35) 

            # --- 3. THE SIDEBAR STICKY-CLICK LOGIC ---
            # Aurora menus can be 'finicky'. We use a loop to ensure 'Roof' opens.
            
            print("LOG: Attempting to trigger AI SmartRoof...")
            
            # Step A: Ensure we are on the 'Site' tab
            await page.locator("div[role='tab']").get_by_text("Site").click(force=True)
            await asyncio.sleep(2)

            # Step B: Click 'Roof' and verify if 'AI SmartRoof' appears
            for attempt in range(3):
                print(f"LOG: Opening Roof Menu (Attempt {attempt+1})...")
                # We target the chevron/arrow next to Roof if text click fails
                await page.locator("li").filter(has_text="Roof").click(force=True)
                await asyncio.sleep(3)
                
                ai_button = page.get_by_text("AI SmartRoof")
                if await ai_button.is_visible():
                    print("LOG: AI SmartRoof visible! Clicking...")
                    await ai_button.click(force=True)
                    break
                else:
                    print("LOG: Menu didn't open, retrying...")
                    # Click somewhere else to 'reset' the menu
                    await page.mouse.click(10, 10) 
            
            # --- 4. WAIT FOR AI TO MODEL ---
            print("LOG: AI Modeling in progress. Waiting for 'complete' status...")
            # This is the yellow progress bar in your video
            await page.wait_for_selector("text=AI SmartRoof complete", timeout=120000)
            print("LOG: AI SmartRoof Finished.")

            # --- 5. RUN AUTODESIGNER (PANELS) ---
            print("LOG: Switching to System tab...")
            await page.locator("div[role='tab']").get_by_text("System").click(force=True)
            await asyncio.sleep(3)
            
            print("LOG: Triggering AutoDesigner...")
            await page.get_by_text("AutoDesigner").click(force=True)
            await asyncio.sleep(2)
            await page.get_by_role("button", name="Run AutoDesigner").click(force=True)

            # --- 6. HANDLE INVERTER ERROR ---
            print("LOG: Checking for Inverter errors...")
            await asyncio.sleep(10)
            
            if await page.get_by_text("Inverter is required").is_visible():
                print("LOG: Inverter Error found. Fixing...")
                await page.locator("div[role='tab']").get_by_text("Site").click(force=True)
                await page.get_by_text("Components").click(force=True)
                await page.get_by_text("Select Inverter").click(force=True)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)
                
                await page.locator("div[role='tab']").get_by_text("System").click(force=True)
                await page.get_by_text("AutoDesigner").click(force=True)
                await page.get_by_role("button", name="Run AutoDesigner").click(force=True)
                await page.wait_for_selector("text=AutoDesigner completed", timeout=60000)

            # --- 7. SALES MODE ---
            print("LOG: Entering Sales Mode...")
            await page.get_by_text("Sales mode").click(force=True)
            
            await asyncio.sleep(15)
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