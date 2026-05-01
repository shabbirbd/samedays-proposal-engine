import asyncio
import os
import base64
import re
from playwright.async_api import async_playwright
from anthropic import Anthropic
from dotenv import load_dotenv

# Load credentials
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def run_aurora_automation(rep_id, customer_name):
    os.environ["DISPLAY"] = ":99"
    print(f"LOG: Starting Vision Agent for {customer_name} (Claude 4.6 Mode)")
    
    async with async_playwright() as p:
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--display=:99", "--window-size=1280,1024"]
        )
        page = await context.new_page()

        try:
            # --- PHASE 1: LOGIN & NAVIGATE ---
            print("LOG: Navigating to Aurora...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            if "login" in page.url:
                print("LOG: Login page detected. Entering credentials...")
                await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
                await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
                await page.get_by_role("button", name="Log in").click()
                print("LOG: [MFA Check] Look at RealVNC if it stops here.")
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
            await asyncio.sleep(30) 

            # --- PHASE 2: UNIVERSAL VISION LOOP ---
            system_prompt = f"""
            You are a solar design expert. Screen resolution: 1280x1024.
            Your goal is to finish the design for {customer_name}.
            
            DIRECTIONS:
            1. Find 'Roof' in the sidebar and click it.
            2. Click 'AI SmartRoof'. 
            3. Wait for modeling to finish (yellow bar at bottom).
            4. Click 'System' tab, then 'AutoDesigner', then 'Run'.
            5. Fix Inverter errors if they appear.
            6. Click 'Sales mode' to finish.
            
            COMMAND FORMAT:
            To move the mouse and click, you MUST output exactly: ACTION: CLICK(x, y)
            To type text, output: ACTION: TYPE("text")
            To wait, output: ACTION: WAIT(5)
            """

            messages = []
            for iteration in range(25):
                print(f"LOG: Iteration {iteration}")
                await asyncio.sleep(2) 
                
                screenshot_path = "agent_view.png"
                await page.screenshot(path=screenshot_path, animations="disabled")
                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                # Regular API call (No tool registration needed)
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=500,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}},
                            {"type": "text", "text": f"Current URL: {page.url}. What is the next ACTION?"}
                        ]
                    }]
                )

                thought = response.content[0].text
                print(f"CLAUDE THOUGHT: {thought}")
                messages.append({"role": "assistant", "content": thought})

                # --- MANUAL ACTION PARSER ---
                # Look for CLICK(x, y)
                click_match = re.search(r"ACTION: CLICK\((\d+),\s*(\d+)\)", thought)
                # Look for TYPE("text")
                type_match = re.search(r'ACTION: TYPE\("([^"]+)"\)', thought)
                # Look for WAIT(s)
                wait_match = re.search(r"ACTION: WAIT\((\d+)\)", thought)

                if click_match:
                    x, y = int(click_match.group(1)), int(click_match.group(2))
                    print(f"ACTION: Clicking {x}, {y}")
                    await page.mouse.click(x, y)
                elif type_match:
                    text = type_match.group(1)
                    print(f"ACTION: Typing {text}")
                    await page.keyboard.type(text)
                elif wait_match:
                    sec = int(wait_match.group(1))
                    print(f"ACTION: Waiting {sec}s")
                    await asyncio.sleep(sec)

                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! {page.url}")
                    return page.url

            return "FAILED: Max iterations"

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            print("LOG: Process complete. VNC alive for 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))