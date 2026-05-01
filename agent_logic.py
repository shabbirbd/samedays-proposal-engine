import asyncio
import os
import base64
from playwright.async_api import async_playwright
from anthropic import Anthropic
from dotenv import load_dotenv

# Force load the .env file
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

# Initialize Anthropic Client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def run_aurora_automation(rep_id, customer_name):
    # Force the script to use the Virtual Display
    os.environ["DISPLAY"] = ":99"
    
    print(f"LOG: Starting Hybrid Agent for {customer_name}")
    
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
                "--disable-dev-shm-usage"
            ]
        )
        page = await context.new_page()

        try:
            # --- PHASE 1: LOGIN & SEARCH (Code-based for speed/cost) ---
            print("LOG: Navigating to Aurora Projects...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Handle Login if necessary
            if "login" in page.url:
                print("LOG: Login page detected. Entering credentials via code...")
                await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
                await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
                await page.get_by_role("button", name="Log in").click()
                
                # Check for MFA
                await asyncio.sleep(5)
                if "mfa" in page.url or await page.get_by_text("Enter code").is_visible():
                    print("LOG: [ACTION REQUIRED] Please enter MFA code in RealVNC.")
                    await page.wait_for_url("**/projects", timeout=120000)
            
            # Search & Open Customer
            print(f"LOG: Searching for '{customer_name}'...")
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.wait_for(state="visible")
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)

            print(f"LOG: Opening project for {customer_name}...")
            await page.get_by_text(customer_name, exact=False).first.click()
            await asyncio.sleep(5)
            
            # Click New Design
            print("LOG: Clicking New Design button...")
            await page.get_by_role("button", name="New design").click()
            
            # Wait for the CAD Engine "Coming right up" screen to pass
            print("LOG: Waiting 30s for CAD Engine. Handing over to Claude...")
            await asyncio.sleep(30) 

            # --- PHASE 2: THE 3D DESIGN (Vision-based for intelligence) ---
            system_prompt = f"""
            You are a solar design expert controlling a computer. 
            Resolution: 1280x1024.
            Goal: Finish the proposal for customer: {customer_name}
            
            DIRECTIONS:
            1. Find the 'Roof' menu in the sidebar and click it.
            2. Click 'AI SmartRoof'. 
            3. Observe the progress. When modeling is complete (yellow bar disappears), proceed.
            4. Click the 'System' tab, then click 'AutoDesigner', then click 'Run AutoDesigner'.
            5. If a red error says 'Inverter required', click 'Components' in the menu, select an inverter, and Run AutoDesigner again.
            6. When finished, click 'Sales mode' in the top right.
            7. Success is reached when the URL contains 'e-proposal'.
            """

            messages = []
            
            for iteration in range(25):
                print(f"LOG: Claude Iteration {iteration} - Analyzing 3D Canvas...")
                await asyncio.sleep(2) 
                
                # Take screenshot for Claude
                screenshot_path = f"agent_view.png"
                await page.screenshot(path=screenshot_path, animations="disabled")

                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                # Call Claude Sonnet 4.6
                response = client.beta.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Current URL: {page.url}. What is the next move in the CAD designer?"},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}}
                        ]
                    }],
                    betas=["computer-use-2024-10-22"]
                )

                messages.append({"role": "user", "content": f"Step {iteration} analysis requested."})
                
                # Execute Claude's visual actions
                for content in response.content:
                    if content.type == "text":
                        print(f"CLAUDE THOUGHT: {content.text}")
                    
                    if content.type == "tool_use" and content.name == "computer":
                        action = content.input["action"]
                        coords = content.input.get("coordinate")
                        text = content.input.get("text")

                        print(f"ACTION: {action} at {coords if coords else text}")

                        if action == "mouse_move":
                            await page.mouse.move(coords[0], coords[1])
                        elif action == "left_click":
                            await page.mouse.click(coords[0], coords[1])
                        elif action == "type":
                            await page.keyboard.type(text, delay=50)
                        elif action == "key":
                            await page.keyboard.press(text)

                # Check if we transitioned to the proposal link
                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! Final Link: {page.url}")
                    return page.url
                
                await asyncio.sleep(2)

            return "FAILED: Max iterations reached."

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            await page.screenshot(path="final_crash_error.png")
            return f"ERROR: {e}"
        finally:
            print("LOG: Process complete. Keeping VNC alive for 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    as