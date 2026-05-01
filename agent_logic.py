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
            args=["--no-sandbox", "--disable-setuid-sandbox", "--display=:99", "--window-size=1280,1024"]
        )
        page = await context.new_page()

        try:
            # --- 1. NAVIGATE (NO WAIT STRATEGY) ---
            print(f"LOG: Navigating to projects...")
            # We don't use 'networkidle' here because it causes the 30s timeout on EC2
            await page.goto("https://v2.aurorasolar.com/projects", timeout=60000)
            
            # Instead, we wait for the Search Bar to appear. This is much faster.
            print("LOG: Waiting for search bar to appear (60s timeout)...")
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.wait_for(state="visible", timeout=60000)
            print("LOG: Page loaded. Search bar found.")

            # Dismiss popups
            try:
                await page.locator("button:has-text('Restore')").click(timeout=3000)
            except: pass

            # --- 2. SEARCH & OPEN ---
            await search_input.click()
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(6)
            
            await page.get_by_text(customer_name, exact=False).first.click()
            print(f"LOG: Opened project for {customer_name}")
            await asyncio.sleep(5)

            # --- 3. OPEN NEW DESIGN ---
            print("LOG: Clicking New Design...")
            await page.get_by_role("button", name="New design").click(force=True)
            
            print("LOG: Waiting for CAD Engine (40s)...")
            await asyncio.sleep(40) 

            # --- 4. THE SIDEBAR CLICK LOOP ---
            print("LOG: Attempting to trigger AI SmartRoof...")
            await page.get_by_text("Site", exact=True).click(force=True)
            await asyncio.sleep(3)

            for attempt in range(3):
                print(f"LOG: Opening Roof Menu (Attempt {attempt+1})...")
                await page.locator("li").filter(has_text="Roof").click(force=True)
                await asyncio.sleep(4)
                
                ai_button = page.get_by_text("AI SmartRoof")
                if await ai_button.is_visible():
                    await ai_button.click(force=True)
                    print("LOG: AI SmartRoof clicked.")
                    break
                else:
                    await page.mouse.click(500, 10) # Click away to reset
                    await asyncio.sleep(2)
            
            # --- 5. WAIT FOR MODELING ---
            await page.wait_for_selector("text=AI SmartRoof complete", timeout=120000)
            print("LOG: AI Modeling finished.")

            # --- 6. SYSTEM -> AUTODESIGNER ---
            await page.get_by_text("System", exact=True).click(force=True)
            await asyncio.sleep(3)
            await page.get_by_text("AutoDesigner").click(force=True)
            await asyncio.sleep(2)
            await page.get_by_role("button", name="Run AutoDesigner").click(force=True)

            # --- 7. HANDLE INVERTER ERROR ---
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

            # --- 8. SALES MODE ---
            print("LOG: Entering Sales Mode...")
            await page.get_by_text("Sales mode").click(force=True)
            await asyncio.sleep(20) 
            
            final_url = page.url
            print(f"LOG: SUCCESS! Final URL: {final_url}")
            return final_url

        except Exception as e:
            print(f"!!! WORKFLOW ERROR: {e}")
            return f"ERROR: {str(e)}"

        finally:
            print("LOG: Keeping browser open for 5 mins for review.")
            await asyncio.sleep(300)
            await context.close()