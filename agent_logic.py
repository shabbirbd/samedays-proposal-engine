import asyncio
import os
import base64
import json
from playwright.async_api import async_playwright
from anthropic import Anthropic
from dotenv import load_dotenv

# Force load the .env file
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def run_aurora_automation(rep_id, customer_name):
    os.environ["DISPLAY"] = ":99"
    print(f"LOG: Starting Hybrid Agent for {customer_name}")
    
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
            # --- PHASE 1: LOGIN & NAVIGATE ---
            print("LOG: Navigating to Aurora...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            if "login" in page.url:
                print("LOG: Login page detected. Entering credentials...")
                await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
                await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
                await page.get_by_role("button", name="Log in").click()
                print("LOG: [ACTION] Handle MFA in VNC if needed.")
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
            
            # --- PHASE 2: CAD PREPARATION (Kickstart) ---
            print("LOG: Waiting for CAD Engine...")
            await asyncio.sleep(30) 

            # KICKSTART: Manually click Site then Roof to help Claude
            try:
                print("LOG: Kickstarting menu...")
                await page.mouse.click(100, 200) # Click Site Tab
                await asyncio.sleep(2)
                await page.mouse.click(100, 240) # Click Roof Menu
                await asyncio.sleep(2)
            except: pass

            # --- PHASE 3: THE VISION LOOP ---
            system_prompt = f"""
            You are a solar design expert. Screen resolution: 1280x1024.
            Goal: Finish the proposal for {customer_name}.
            
            DIRECTIONS:
            1. Click 'Roof' -> 'AI SmartRoof'. Wait for yellow bar to vanish.
            2. Click 'System' -> 'AutoDesigner' -> 'Run'.
            3. Fix Inverter errors if they appear.
            4. Click 'Sales mode' to finish.
            
            IMPORTANT: Use the 'computer' tool for all actions. 
            If you click and nothing happens, try clicking 10 pixels to the right.
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

                # Request Action
                response = client.beta.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"URL: {page.url}. Perform next move."},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}}
                        ]
                    }],
                    betas=["computer-use-2024-10-22"]
                )

                messages.append({"role": "user", "content": f"Step {iteration} requested."})
                
                # --- ROBUST TOOL PARSER ---
                for content in response.content:
                    if content.type == "text":
                        print(f"CLAUDE THOUGHT: {content.text}")
                    
                    # Some models put tool calls in text, some in tool_use. We handle both.
                    if content.type == "tool_use":
                        # Standard Computer Use Tool
                        if content.name == "computer":
                            action = content.input.get("action")
                            coords = content.input.get("coordinate")
                            text = content.input.get("text")
                            
                            print(f"ACTION: {action} at {coords}")
                            if action == "left_click" and coords:
                                await page.mouse.click(coords[0], coords[1])
                            elif action == "mouse_move" and coords:
                                await page.mouse.move(coords[0], coords[1])
                            elif action == "type" and text:
                                await page.keyboard.type(text)

                        # Handle if model calls "click" or "type" directly (Fallback)
                        elif content.name in ["click", "left_click"]:
                            x = content.input.get("x") or content.input.get("coordinate", [0,0])[0]
                            y = content.input.get("y") or content.input.get("coordinate", [0,0])[1]
                            print(f"ACTION (Direct Click): {x}, {y}")
                            await page.mouse.click(int(x), int(y))

                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! {page.url}")
                    return page.url
                
                await asyncio.sleep(1)

            return "FAILED: Max iterations"

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            print("LOG: Process finished. Closing in 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))