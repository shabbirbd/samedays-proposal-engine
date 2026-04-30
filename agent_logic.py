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
            # --- 1. SEARCH & OPEN CUSTOMER (Already working) ---
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)
            await page.locator(f"text='{customer_name}'").first.click()
            
            # --- 2. CLICK NEW DESIGN ---
             print("LOG: Opening New Design...")
        new_design_btn = page.get_by_role("button", name="New design")
        await new_design_btn.wait_for(state="visible")
        await new_design_btn.click()
        
        # CRITICAL: Close the 'Restore pages' pop-up if it exists
        try:
            print("LOG: Checking for Chromium restore pop-up...")
            await page.get_by_role("button", name="Restore").click(timeout=5000)
        except:
            print("LOG: No restore pop-up found, continuing.")

        # Wait for the 3D Engine to load completely
        print("LOG: Waiting for 3D Engine to be ready...")
        await asyncio.sleep(20) 

        # --- 3. RUN AI SMARTROOF ---
        print("LOG: Attempting to open Roof menu...")
        try:
            # In your screenshot, 'Roof' is a clear menu item. 
            # We use a combined selector to ensure we hit the right one.
            roof_menu = page.locator("div").get_by_text("Roof", exact=True).first
            await roof_menu.wait_for(state="visible", timeout=20000)
            
            # Visual Debug: Highlight the Roof button
            await roof_menu.evaluate("el => el.style.border = '3px solid red'")
            await roof_menu.click()
            print("LOG: Roof menu clicked.")
            
            await asyncio.sleep(2)
            
            # Now click AI SmartRoof
            print("LOG: Clicking AI SmartRoof...")
            ai_smartroof_btn = page.get_by_text("AI SmartRoof").first
            await ai_smartroof_btn.click()
            
            # Wait for the progress bar
            print("LOG: AI modeling in progress...")
            # We look for the "Running AI SmartRoof" status at the bottom
            await page.wait_for_selector("text=AI SmartRoof complete", timeout=120000)
            print("LOG: AI SmartRoof modeling successful.")

        except Exception as e:
            print(f"LOG: Failed to interact with Roof menu. Error: {e}")
            await page.screenshot(path="cad_error.png")

        # --- 4. RUN AUTODESIGNER ---
        print("LOG: Navigating to System menu...")
        # Clicking 'System' tab at the top of the menu box
        await page.get_by_text("System", exact=True).click()
        await asyncio.sleep(2)
        
        await page.get_by_text("AutoDesigner").click()
        await page.get_by_role("button", name="Run AutoDesigner").click()
            
            # Highlight the 'Run AutoDesigner' button
            run_btn = page.get_by_role("button", name="Run AutoDesigner")
            await run_btn.evaluate("el => el.style.border = '4px solid green'")
            await run_btn.click()

            # --- 5. HANDLE INVERTER ERROR (Video @ 0:50) ---
            print("LOG: Checking for Inverter Error...")
            await asyncio.sleep(6) # Wait for the error toast to potentially appear
            
            error_exists = await page.get_by_text("Inverter is required").is_visible()
            if error_exists:
                print("LOG: ERROR FOUND: Inverter required. Fixing...")
                await page.get_by_text("Components").click()
                await page.get_by_text("Select Inverter").click()
                # Select the first option (Tesla or Enphase)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                # Run AutoDesigner again
                await page.get_by_role("button", name="Run AutoDesigner").click()
                await page.wait_for_selector("text=AutoDesigner completed", timeout=60000)

            # --- 6. GENERATE PROPOSAL LINK ---
            print("LOG: Design done. Entering Sales Mode...")
            await page.get_by_text("Sales mode").click()
            
            # Wait for the proposal to load
            await asyncio.sleep(10)
            
            final_proposal_url = page.url
            print(f"LOG: SUCCESS! Final URL: {final_proposal_url}")
            
            # Send this URL back to your main app (or just return it)
            return final_proposal_url

        except Exception as e:
            print(f"!!! WORKFLOW ERROR: {e}")
            await page.screenshot(path="workflow_error.png")

        # Keep open for review
        print("LOG: Keeping browser open for 5 minutes.")
        await asyncio.sleep(300)
        return "SUCCESS"