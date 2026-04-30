import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def run_aurora_automation(rep_id, customer_name):
    async with async_playwright() as p:
        # Each rep gets their own folder to save cookies
        profile_path = f"/home/ubuntu/samedays-agent/profiles/{rep_id}"
        
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

        print(f"LOG: Navigating to Aurora for customer: {customer_name}")
        await page.goto("https://v2.aurorasolar.com/projects", timeout=60000)
        await asyncio.sleep(5)

        # 1. HANDLE LOGIN
        if "login" in page.url:
            print("LOG: Login required. Filling form...")
            await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
            await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
            await page.get_by_role("button", name="Log in").click()
            
            # Wait to see if MFA appears
            await asyncio.sleep(5)
            if "mfa" in page.url or page.get_by_text("Enter code").is_visible():
                print("LOG: MFA DETECTED. Please enter the code in RealVNC now.")
                # We wait up to 2 minutes for you to type it in VNC
                try:
                    await page.wait_for_url("**/projects", timeout=120000)
                    print("LOG: MFA success. Session saved.")
                except:
                    print("LOG: MFA Timeout.")
                    return "MFA_TIMEOUT"

        # 2. SEARCH CUSTOMER
        print(f"LOG: Searching for {customer_name}...")
        search_box = page.get_by_placeholder("Search projects")
        await search_box.wait_for(state="visible")
        await search_box.fill(customer_name)
        await page.keyboard.press("Enter")
        await asyncio.sleep(4)

        # 3. CLICK CUSTOMER
        print(f"LOG: Selecting customer from list...")
        try:
            # This clicks the first row in the table that matches the name
            customer_row = page.get_by_text(customer_name, exact=False).first
            await customer_row.click()
            print("LOG: Successfully opened customer project page.")
            
            # Take a success screenshot for verification
            await page.screenshot(path="success_click.png")
            
        except Exception as e:
            print(f"ERROR: Could not click customer. {e}")
            return "CLICK_FAILED"

        await asyncio.sleep(5)
        await context.close()
        return "SUCCESS"