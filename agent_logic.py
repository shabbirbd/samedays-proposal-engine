import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load credentials
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
                "--disable-infobars" # Attempt to disable 'Restore' popups
            ]
        )
        page = await context.new_page()

        try:
            # --- 1. NAVIGATION ---
            print("LOG: Navigating to projects...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            # NUKE the 'Restore' pop-up immediately
            try:
                restore_btn = page.get_by_role("button", name="Restore")
                if await restore_btn.is_visible():
                    print("LOG: Dismissing Chromium restore popup...")
                    await restore_btn.click(timeout=3000)
            except: pass

            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)
            await page.locator(f"text='{customer_name}'").first.click()
            
            # --- 2. OPEN DESIGN ---
            print("LOG: Opening New Design...")
            # Wait for any existing design or the button
            await page.get_by_role("button", name="New design").click()
            
            # CRITICAL: Wait for the "Coming right up" screen to vanish
            print("LOG: Waiting for 3D CAD Engine (35s)...")
            await asyncio.sleep(35) 

            # --- 3. INTERACTING WITH THE SIDEBAR ---
            print("LOG: Selecting 'Site' tab...")
            # Aurora uses tabs for Site/System. We click 'Site' to be sure.
            await page.locator("div[role='tab']").get_by_text("Site").click(force=True)
            await asyncio.sleep(2)

            # CLICK ROOF MENU
            print("LOG: Attempting to open Roof sub-menu...")
            # We target the specific list item that contains 'Roof'
            roof_item = page.locator("li").filter(has_text="Roof").first
            await roof_item.scroll_into_view_if_needed()
            await roof_item.click(force=True)
            await asyncio.sleep(3)

            # TAKE DEBUG SCREENSHOT to see if menu opened
            await page.screenshot(path="after_roof_click.png")

            # CLICK AI SMARTROOF
            print("LOG: Looking for AI SmartRoof...")
            # Using exact=False to catch potential TM symbols
            ai_btn = page.get_by_text("AI SmartRoof", exact=False).first
            await ai_btn.wait_for(state="visible", timeout=15000)
            await ai_btn.click(force=True)
            
            print("LOG: AI modeling started. Waiting for completion (up to 2 mins)...")
            # The yellow bar in your video. We wait for the 'complete' status.
            await page.wait_for_selector("text=AI SmartRoof complete", timeout=120000)
            print("LOG: AI SmartRoof modeling successful.")

            # --- 4. SYSTEM -> AUTODESIGNER ---
            print("LOG: Switching to System tab...")
            await page.locator("div[role='tab']").get_by_text("System").click(force=True)
            await asyncio.sleep(3)
            
            print("LOG: Opening AutoDesigner...")
            await page.get_by_text("AutoDesigner").click(force=True)
            await asyncio.sleep(2)
            
            print("LOG: Running AutoDesigner...")
            await page.get_by_role("button", name="Run AutoDesigner").click(force=True)

            # --- 5. HANDLE INVERTER ERROR ---
            print("LOG: Waiting for Inverter Error check...")
            await asyncio.sleep(8) 
            
            if await page.get_by_text("Inverter is required").is_visible():
                print("LOG: Inverter Error detected. Fixing...")
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

            # --- 6. SALES MODE ---
            print("LOG: Entering Sales Mode...")
            await page.get_by_text("Sales mode").click(force=True)
            
            # Wait for proposal link to generate
            await asyncio.sleep(15)
            
            final_url = page.url
            print(f"LOG: SUCCESS! URL: {final_url}")
            return final_url

        except Exception as e:
            print(f"!!! WORKFLOW ERROR: {e}")
            await page.screenshot(path="cad_crash.png")
            return f"ERROR: {str(e)}"

        finally:
            print("LOG: Keeping VNC alive for 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))