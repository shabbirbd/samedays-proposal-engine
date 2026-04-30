import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

async def run_aurora_automation(rep_id, customer_name):
    print(f"LOG: Starting design workflow for {customer_name}")
    
    async with async_playwright() as p:
        # Path where cookies are stored for this rep
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        # Launch browser connected to virtual display :99
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
            # --- STEP 1: NAVIGATION & LOGIN ---
            print(f"LOG: Navigating to Projects page...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Check if we are redirected to login
            if "login" in page.url:
                print("LOG: Session expired. Logging in automatically...")
                await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
                await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
                await page.get_by_role("button", name="Log in").click()
                
                # Check for MFA
                await asyncio.sleep(5)
                if "mfa" in page.url or page.get_by_text("Enter code").is_visible():
                    print("LOG: [ACTION REQUIRED] Please enter the MFA code in RealVNC now.")
                    # Wait for you to type code and browser to redirect to projects
                    try:
                        await page.wait_for_url("**/projects", timeout=120000)
                        print("LOG: Login successful via MFA.")
                    except:
                        print("LOG: Login timeout.")
                        return "LOGIN_FAILED"

            # --- STEP 2: SEARCH & OPEN CUSTOMER ---
            print(f"LOG: Searching for '{customer_name}'...")
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.wait_for(state="visible", timeout=20000)
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)

            print(f"LOG: Clicking customer result...")
            await page.get_by_text(customer_name, exact=False).first.click()
            await asyncio.sleep(5)
            
            # --- STEP 3: CREATE NEW DESIGN ---
            print("LOG: Clicking New Design button...")
            new_design_btn = page.get_by_role("button", name="New design")
            await new_design_btn.wait_for(state="visible")
            await new_design_btn.click()
            
            # Handle Chromium "Restore pages" pop-up
            try:
                restore_btn = page.get_by_role("button", name="Restore")
                if await restore_btn.is_visible():
                    await restore_btn.click(timeout=3000)
            except:
                pass

            # Wait for the 3D Engine "Coming right up" screen to pass
            print("LOG: Waiting 25 seconds for CAD Engine to load...")
            await asyncio.sleep(25) 

            # --- STEP 4: RUN AI SMARTROOF ---
            print("LOG: Attempting AI SmartRoof...")
            try:
                # Open Roof Menu
                roof_menu = page.locator("div").get_by_text("Roof", exact=True).first
                await roof_menu.wait_for(state="visible", timeout=20000)
                await roof_menu.click()
                await asyncio.sleep(2)
                
                # Click AI SmartRoof
                await page.get_by_text("AI SmartRoof").first.click()
                
                # Wait for yellow progress bar completion
                print("LOG: AI modeling roof planes... (be patient)")
                await page.wait_for_selector("text=AI SmartRoof complete", timeout=120000)
                print("LOG: AI SmartRoof successful.")
            except Exception as e:
                print(f"LOG: AI SmartRoof failed or already completed. Error: {e}")

            # --- STEP 5: RUN AUTODESIGNER (PANELS) ---
            print("LOG: Navigating to System menu...")
            await page.get_by_text("System", exact=True).click()
            await asyncio.sleep(2)
            
            await page.get_by_text("AutoDesigner").click()
            print("LOG: Clicking Run AutoDesigner...")
            await page.get_by_role("button", name="Run AutoDesigner").click()

            # --- STEP 6: HANDLE INVERTER ERROR (Video @ 0:50) ---
            print("LOG: Checking for errors...")
            await asyncio.sleep(6) 
            
            if await page.get_by_text("Inverter is required").is_visible():
                print("LOG: Detected Inverter Error. Applying fix...")
                await page.get_by_text("Components").click()
                await page.get_by_text("Select Inverter").click()
                
                # Select first inverter in list
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                
                # Try again
                print("LOG: Re-running AutoDesigner...")
                await page.get_by_role("button", name="Run AutoDesigner").click()
                await page.wait_for_selector("text=AutoDesigner completed", timeout=60000)

            # --- STEP 7: FINISH & GET SALES LINK ---
            print("LOG: Entering Sales Mode...")
            await page.get_by_text("Sales mode").click()
            
            # Wait for Sales Mode URL generation
            await asyncio.sleep(15)
            
            final_url = page.url
            print(f"LOG: SUCCESS! Final Link: {final_url}")
            
            return final_url

        except Exception as e:
            print(f"!!! WORKFLOW ERROR: {e}")
            await page.screenshot(path="error_debug.png")
            return f"ERROR: {str(e)}"

        finally:
            # We keep the browser open for 5 minutes so you can watch in VNC
            print("LOG: Task finished. Keeping VNC alive for 5 minutes.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))