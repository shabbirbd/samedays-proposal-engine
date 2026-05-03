import asyncio
import os
import base64
import re
from playwright.async_api import async_playwright
from anthropic import Anthropic
from dotenv import load_dotenv

# Force load the .env file
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def run_aurora_automation(rep_id, customer_name):
    os.environ["DISPLAY"] = ":99"
    print(f"LOG: Starting Optimized Workflow for {customer_name}")
    
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
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--disable-session-crashed-bubble", # Try to disable the restore bubble at startup
            ]
        )
        page = await context.new_page()

        try:
            # --- PHASE 1: LOGIN & NAVIGATE ---
            print("LOG: Navigating to Aurora...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            
            # --- POPUP NUKE: Remove the Restore Bubble immediately ---
            await asyncio.sleep(3)
            try:
                # Target the 'X' or the 'Restore' button if it exists
                restore_close = page.locator("button[aria-label='Close'], .infobar-close, button:has-text('Restore')").first
                if await restore_close.is_visible():
                    print("LOG: Dismissing Chrome Restore popup...")
                    await restore_close.click()
            except: pass

            if "login" in page.url:
                await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
                await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
                await page.get_by_role("button", name="Log in").click()
                print("LOG: [ACTION] Handle MFA in VNC if prompted.")
                await page.wait_for_url("**/projects", timeout=120000)
            
            print(f"LOG: Searching for '{customer_name}'...")
            search = page.locator("input[placeholder*='Search']").first
            await search.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)

            print(f"LOG: Opening project...")
            await page.get_by_text(customer_name, exact=False).first.click()
            await asyncio.sleep(5)
            
            print("LOG: Creating NEW design...")
            await page.get_by_role("button", name="New design").click()
            
            # CAD preparation wait
            await asyncio.sleep(40) 

            # --- PHASE 2: THE VISION LOOP (Claude Sonnet 4.6) ---
            system_prompt = f"""
            You are a solar design expert. Screen resolution: 1280x1024.
            Goal: Create a proposal for {customer_name}. 
            
            CRITICAL RULES TO PREVENT LOOPING:
            1. If you see panels already placed on the roof, STEP 1 and 2 are DONE. 
            2. If 'AutoDesigner completed' is visible, IMMEDIATELY move to the Finance (Dollar) icon.
            3. NEVER click 'Run AutoDesigner' more than once per design.
            4. Skip the Battery icon entirely.

            STEP-BY-STEP CHECKLIST:
            1. ROOF: Click 'Roof' (left sidebar) -> 'AI SmartRoof'. Wait for the yellow bar to finish.
            2. HARDWARE: Click 'System' (left sidebar) -> 'AutoDesigner'.
               - Click 'Select solar panels'. Choose the option starting with 'GL_'.
               - Click 'Select microinverters'. Choose the option starting with 'GL_'.
               - Click the black 'Run AutoDesigner' button.
            3. FINANCE: Once panels are visible, click the 'Dollar Sign' icon in the TOP CENTER.
               - Click 'Adjust financing'.
               - First Dropdown: Select 'GoodLeap'.
               - ACTION: WAIT(5) - You MUST wait 5 seconds for the products to load.
               - Second Dropdown: Select 'GoodLeap PPA Solar + EnergyShift Battery'.
               - Click 'Next' -> Select a Solar Rate -> Click 'Save'.
            4. FINISH: Click 'Sales mode' in the top right.
            
            COMMAND FORMAT:
            ACTION: CLICK(x, y)
            ACTION: TYPE("text")
            ACTION: WAIT(5)
            """

            messages = []
            for iteration in range(50):
                print(f"LOG: Iteration {iteration}")
                await asyncio.sleep(2) 
                
                screenshot_path = "agent_view.png"
                await page.screenshot(path=screenshot_path, animations="disabled")
                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=800,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}},
                            {"type": "text", "text": f"Current URL: {page.url}. If panels are on the roof, click the Dollar icon now."}
                        ]
                    }]
                )

                thought = response.content[0].text
                print(f"CLAUDE THOUGHT: {thought}")
                messages.append({"role": "assistant", "content": thought})

                # --- ACTION PARSER ---
                click_match = re.search(r"ACTION: CLICK\((\d+),\s*(\d+)\)", thought)
                type_match = re.search(r'ACTION: TYPE\("([^"]+)"\)', thought)
                wait_match = re.search(r"ACTION: WAIT\((\d+)\)", thought)

                if click_match:
                    x, y = int(click_match.group(1)), int(click_match.group(2))
                    print(f"EXECUTING: Click at {x}, {y}")
                    await page.mouse.click(x, y)
                elif type_match:
                    text = type_match.group(1)
                    print(f"EXECUTING: Type '{text}'")
                    await page.keyboard.type(text, delay=50)
                elif wait_match:
                    sec = int(wait_match.group(1))
                    print(f"EXECUTING: Wait {sec}s")
                    await asyncio.sleep(sec)

                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! URL: {page.url}")
                    return page.url

            return "FAILED: Max iterations"

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            print("LOG: Final VNC review. Closing in 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))