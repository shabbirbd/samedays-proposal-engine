import asyncio
import os
import base64
from playwright.async_api import async_playwright
from anthropic import Anthropic
from dotenv import load_dotenv

# Force load the .env file from the current directory
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

# Initialize Anthropic Client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def run_aurora_automation(rep_id, customer_name):
    # CRITICAL: Force the script to use the Virtual Display
    os.environ["DISPLAY"] = ":99"
    
    print(f"LOG: Starting Full OpenClaw Agent for {customer_name}")
    
    async with async_playwright() as p:
        # Path where cookies are stored for this rep
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        # Launch browser with stability flags for t3.medium
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--display=:99", 
                "--window-size=1280,1024",
                "--disable-dev-shm-usage", # Use disk instead of shared memory
                "--disable-gpu"            # Force software rendering
            ]
        )
        page = await context.new_page()

        try:
            # Step 1: Open Aurora (Use a 60s timeout for slow EC2 starts)
            print("LOG: Opening Aurora Projects...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            
            # Give the initial page 10 seconds to finish rendering fonts/3D assets
            await asyncio.sleep(10)

            system_prompt = f"""
            You are a solar design expert controlling a computer. 
            Resolution: 1280x1024.
            Goal: Create a proposal for customer: {customer_name}
            
            WORKFLOW:
            1. LOGIN: If you see a login screen, type email '{os.getenv("AURORA_EMAIL")}' and password '{os.getenv("AURORA_PASSWORD")}'.
            2. MFA: If a 6-digit code is needed, stop and wait for the human to type it in RealVNC.
            3. SEARCH: Type '{customer_name}' in the project search bar and press Enter.
            4. OPEN: Click on the customer name '{customer_name}' in the list.
            5. DESIGN: Click '+ New Design'. 
            6. ROOF: Click 'Roof' menu -> 'AI SmartRoof'. Wait for the yellow bar to finish.
            7. SYSTEM: Click 'System' tab -> 'AutoDesigner' -> 'Run'.
            8. ERROR: If 'Inverter required' appears, click 'Components', pick any inverter, and Run again.
            9. FINISH: Click 'Sales mode' in the top right. Success is a URL with 'e-proposal'.
            """

            messages = []
            
            # We allow up to 30 steps
            for iteration in range(30):
                print(f"LOG: Iteration {iteration} - Analyzing Screen...")
                
                # Stability: Wait for any animations to settle
                await asyncio.sleep(2) 
                
                try:
                    screenshot_path = f"agent_view.png"
                    # 'animations="disabled"' prevents the "Unable to capture screenshot" error
                    await page.screenshot(path=screenshot_path, animations="disabled")
                except Exception as screenshot_err:
                    print(f"LOG: Screenshot failed, retrying... {screenshot_err}")
                    await asyncio.sleep(5)
                    continue

                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                # Call Claude Computer Use
                response = client.beta.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Current URL: {page.url}. Perform the next step."},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}}
                        ]
                    }],
                    betas=["computer-use-2024-10-22"]
                )

                # Execute Claude's decision
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

                # Check if we hit the success URL
                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! Goal reached: {page.url}")
                    return page.url
                
                await asyncio.sleep(2)

            return "FAILED: Max iterations reached."

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            # We keep VNC open for 5 minutes so you can watch
            print("LOG: Process complete. Keeping VNC alive for 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))