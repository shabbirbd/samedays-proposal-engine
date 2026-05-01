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
            # --- 1. NAVIGATION ---
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            # Handle possible Chromium crash popup immediately
            try:
                await page.get_by_role("button", name="Restore").click(timeout=3000)
            except: pass

            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)
            await page.locator(f"text='{customer_name}'").first.click()
            
            # --- 2. OPEN DESIGN ---
            print("LOG: Opening New Design...")
            await page.get_by_role("button", name="New design").click()
            
            # CRITICAL: Wait for CAD load
            print("LOG: Waiting for 3D Engine to initialize (30s)...")
            await asyncio.sleep(30) 

            # --- 3. SITE -> ROOF -> AI SMARTROOF ---
            print("LOG: Navigating Site menu...")
            # Click 'Site' tab first to ensure menu is active
            await page.get_by_text("Site", exact=True).click(force=True)
            await asyncio.sleep(2)
            
            # Open Roof menu
            print("LOG: Clicking Roof menu...")
            roof_btn = page.locator("div").get_by_text("Roof", exact=True).first
            await roof_btn.click(force=True)
            await asyncio.sleep(2)
            
            # Click AI SmartRoof
            print("LOG: Triggering AI SmartRoof...")
            await page.get_by_text("AI SmartRoof").first.click(force=True)
            
            # WAIT FOR COMPLETION (Yellow bar in your video)
            print("LOG: AI is modeling. Waiting for 'Complete' toast...")
            # We wait for the specific 'complete' text or for 90 seconds
            try:
                await page.wait_for_selector("text=AI SmartRoof complete", timeout=90000)
                print("LOG: AI SmartRoof modeling finished.")
            except:
                print("LOG: Modeling timeout, but attempting to continue...")

            # --- 4. SYSTEM -> AUTODESIGNER ---
            print("LOG: Switching to System tab...")
            await page.get_by_text("System", exact=True).click(force=True)
            await asyncio.sleep(3)
            
            print("LOG: Opening AutoDesigner...")
            await page.get_by_text("AutoDesigner").click(force=True)
            await asyncio.sleep(2)
            
            # Now click 'Run AutoDesigner' in the slide-out menu
            print("LOG: Running AutoDesigner (Placing Panels)...")
            run_btn = page.get_by_role("button", name="Run AutoDesigner")
            await run_btn.wait_for(state="visible")
            await run_btn.click(force=True)

            # --- 5. HANDLE INVERTER ERROR (Video @ 0:50) ---
            print("LOG: Monitoring for Inverter Error...")
            await asyncio.sleep(8) # Wait for simulation to run
            
            if await page.get_by_text("Inverter is required").is_visible():
                print("LOG: DETECTED: Inverter error. Fixing...")
                # Go to Components (Site menu)
                await page.get_by_text("Site", exact=True).click(force=True)
                await page.get_by_text("Components").click(force=True)
                await page.get_by_text("Select Inverter").click(force=True)
                
                # Pick the first one
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)
                
                # Go back to System and Run again
                await page.get_by_text("System", exact=True).click(force=True)
                await page.get_by_text("AutoDesigner").click(force=True)
                await page.get_by_role("button", name="Run AutoDesigner").click(force=True)
                print("LOG: Re-run triggered after fix.")
                await page.wait_for_selector("text=AutoDesigner completed", timeout=60000)

            # --- 6. SALES MODE ---
            print("LOG: Entering Sales Mode...")
            await page.get_by_text("Sales mode").click(force=True)
            
            # Wait for proposal engine to generate the dynamic URL
            await asyncio.sleep(15)
            
            final_url = page.url
            print(f"LOG: SUCCESS! URL: {final_url}")
            return final_url

        except Exception as e:
            print(f"!!! WORKFLOW ERROR: {e}")
            await page.screenshot(path="cad_crash.png")
            return f"ERROR: {str(e)}"

        finally:
            print("LOG: Final check in RealVNC. Closing in 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))