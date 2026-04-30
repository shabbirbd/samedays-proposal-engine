import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

async def run_aurora_automation(rep_id, customer_name):
    print(f"LOG: Starting design workflow for {customer_name}")
    
    async with async_playwright() as p:
        # Define the path where cookies are stored for this rep
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        # Launch browser connected to the virtual display :99
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
            # --- STEP 1: SEARCH & OPEN CUSTOMER ---
            print(f"LOG: Navigating to Projects page...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded")
            await asyncio.sleep(5)

            print(f"LOG: Searching for '{customer_name}'...")
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)

            print(f"LOG: Clicking customer result...")
            await page.get_by_text(customer_name, exact=False).first.click()
            
            # --- STEP 2: HANDLE DESIGN CREATION ---
            print("LOG: Clicking New Design button...")
            new_design_btn = page.get_by_role("button", name="New design")
            await new_design_btn.wait_for(state="visible")
            await new_design_btn.click()
            
            # --- STEP 3: HANDLE BROWSER POP-UPS ---
            # This handles the "Chromium didn't shut down correctly" blue button
            try:
                print("LOG: Checking for 'Restore pages' pop-up...")
                restore_btn = page.get_by_role("button", name="Restore")
                if await restore_btn.is_visible():
                    await restore_btn.click(timeout=5000)
                    print("LOG: Restore pop-up dismissed.")
            except:
                print("LOG: No restore pop-up detected.")

            # Wait for the 3D Engine to load completely
            print("LOG: Waiting 20 seconds for 3D Engine to load...")
            await asyncio.sleep(20) 

            # --- STEP 4: RUN AI SMARTROOF ---
            print("LOG: Attempting to open Roof menu...")
            try:
                # Target the 'Roof' menu in the sidebar
                roof_menu = page.locator("div").get_by_text("Roof", exact=True).first
                await roof_menu.wait_for(state="visible", timeout=20000)
                
                # Visual Highlight for VNC debugging
                await roof_menu.evaluate("el => el.style.border = '3px solid red'")
                await roof_menu.click()
                print("LOG: Roof menu opened.")
                
                await asyncio.sleep(2)
                
                print("LOG: Clicking AI SmartRoof...")
                await page.get_by_text("AI SmartRoof").first.click()
                
                # Wait for progress bar (Yellow bar in your video)
                print("LOG: AI is modeling the roof. Waiting for completion...")
                await page.wait_for_selector("text=AI SmartRoof complete", timeout=120000)
                print("LOG: AI SmartRoof successful.")
            except Exception as e:
                print(f"LOG: Error in AI SmartRoof step: {e}")

            # --- STEP 5: RUN AUTODESIGNER (PANELS) ---
            print("LOG: Navigating to System menu...")
            await page.get_by_text("System", exact=True).click()
            await asyncio.sleep(2)
            
            await page.get_by_text("AutoDesigner").click()
            
            print("LOG: Running AutoDesigner...")
            run_btn = page.get_by_role("button", name="Run AutoDesigner")
            await run_btn.click()

            # --- STEP 6: HANDLE INVERTER ERROR (Video @ 0:50) ---
            print("LOG: Checking for Inverter Error...")
            await asyncio.sleep(6) 
            
            error_msg = page.get_by_text("Inverter is required")
            if await error_msg.is_visible():
                print("LOG: Detected Inverter Error. Applying fix...")
                await page.get_by_text("Components").click()
                await page.get_by_text("Select Inverter").click()
                
                # Keyboard navigation to pick the first inverter
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                
                # Run AutoDesigner again after fix
                print("LOG: Re-running AutoDesigner...")
                await page.get_by_role("button", name="Run AutoDesigner").click()
                await page.wait_for_selector("text=AutoDesigner completed", timeout=60000)

            # --- STEP 7: GENERATE FINAL PROPOSAL LINK ---
            print("LOG: Entering Sales Mode...")
            await page.get_by_text("Sales mode").click()
            
            # Give the proposal page 12 seconds to load and generate the URL
            await asyncio.sleep(12)
            
            final_url = page.url
            print(f"LOG: SUCCESS! Final Proposal URL: {final_url}")
            
            return final_url

        except Exception as e:
            print(f"!!! CRITICAL WORKFLOW ERROR: {e}")
            # Save a screenshot for debugging
            await page.screenshot(path="workflow_crash.png")
            return f"ERROR: {str(e)}"

        finally:
            # We keep the browser open for 5 minutes so you can see the result in VNC
            # In a production environment, you would remove this sleep.
            print("LOG: Keeping browser open for 5 minutes for RealVNC inspection.")
            await asyncio.sleep(300)
            await context.close()

# If running this file directly for testing
if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))