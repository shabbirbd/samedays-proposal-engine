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
    print(f"LOG: Starting Hybrid Agent for {customer_name} (Inverter Fix Mode)")
    
    async with async_playwright() as p:
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox", "--display=:99", 
                "--window-size=1280,1024", "--disable-dev-shm-usage"
            ]
        )
        page = await context.new_page()

        try:
            # --- PHASE 1: LOGIN & NAVIGATE (Playwright - Fast/Free) ---
            print("LOG: Navigating to Aurora...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            if "login" in page.url:
                print("LOG: Login page detected. Entering credentials...")
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
            
            print("LOG: Clicking New Design...")
            await page.get_by_role("button", name="New design").click()
            
            # --- PHASE 2: CAD PREPARATION ---
            print("LOG: Waiting for CAD Engine (40s)...")
            await asyncio.sleep(40) 

            # Dismiss "Restore" popup if it's blocking the view
            try:
                await page.get_by_role("button", name="Restore").click(timeout=3000)
            except: pass

            # --- PHASE 3: THE VISION LOOP (Claude Sonnet 4.6) ---
            system_prompt = f"""
            You are a solar design expert. Screen resolution: 1280x1024.
            Goal: Complete the AutoDesign for {customer_name}.
            
            WORKFLOW DIRECTIONS:
            1. ROOF: Click 'Roof' -> 'AI SmartRoof'. Wait for the yellow bar at bottom to disappear.
            2. SYSTEM: Click the 'System' tab in the left sidebar.
            3. AUTODESIGNER: Click 'AutoDesigner' in the menu. This opens a panel on the RIGHT side.
            4. INVERTER: In the RIGHT panel, look for 'Select string inverters' or 'Select microinverters'. 
               - Click that dropdown.
               - Click the first inverter option that appears.
            5. RUN: Click the black 'Run AutoDesigner' button at the bottom right of the sidebar.
            6. FINISH: Click 'Sales mode' in the top right to finish.
            
            COMMAND FORMAT:
            You MUST respond with one action at a time in this format:
            ACTION: CLICK(x, y)
            ACTION: TYPE("text")
            ACTION: WAIT(5)
            
            If you click and nothing happens, try clicking 10 pixels to the right or left.
            """

            messages = []
            
            for iteration in range(25):
                print(f"LOG: Iteration {iteration}")
                await asyncio.sleep(2) 
                
                # Capture Screen
                screenshot_path = "agent_view.png"
                await page.screenshot(path=screenshot_path, animations="disabled")
                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                # Request Action from Claude 4.6
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=600,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}},
                            {"type": "text", "text": f"URL: {page.url}. What is the next ACTION to select the inverter and run the design?"}
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
                    print(f"LOG: SUCCESS! Goal reached: {page.url}")
                    return page.url

            return "FAILED: Max iterations"

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            await page.screenshot(path="final_crash.png")
            return f"ERROR: {e}"
        finally:
            print("LOG: Process finished. VNC remains open for 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))