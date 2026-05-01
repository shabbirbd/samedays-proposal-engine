import asyncio
import os
import base64
from playwright.async_api import async_playwright
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Setup Anthropic Client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def run_aurora_automation(rep_id, customer_name):
    print(f"LOG: Starting OpenClaw Agent for {customer_name}")
    
    async with async_playwright() as p:
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--display=:99", "--window-size=1280,1024"]
        )
        page = await context.new_page()

        try:
            # 1. High-Speed Navigation (Playwright)
            print("LOG: Navigating to projects...")
            await page.goto("https://v2.aurorasolar.com/projects", timeout=60000)
            await asyncio.sleep(5)

            # Handle Login if necessary
            if "login" in page.url:
                await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
                await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
                await page.get_by_role("button", name="Log in").click()
                await page.wait_for_url("**/projects", timeout=60000)

            # Search & Open
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)
            await page.get_by_text(customer_name, exact=False).first.click()
            await asyncio.sleep(5)
            
            # Click New Design
            await page.get_by_role("button", name="New design").click()
            print("LOG: CAD Engine loading. Handing over to Claude (OpenClaw Mode)...")
            await asyncio.sleep(25) 

            # 2. OpenClaw Mode (Claude Computer Use)
            # We give Claude a loop to look at the screen and click
            
            system_prompt = f"""
            You are controlling a web browser to complete a solar design in Aurora.
            Your current task is: 
            1. Click the 'Roof' menu in the sidebar.
            2. Click 'AI SmartRoof'. 
            3. Wait for the 'AI SmartRoof complete' message (yellow bar).
            4. Click the 'System' tab, then 'AutoDesigner', then 'Run AutoDesigner'.
            5. If you see a red 'Inverter is required' error, click 'Components', pick an inverter, and Run AutoDesigner again.
            6. When finished, click 'Sales mode' to generate the proposal.
            
            Important: Only use the 'computer' tool. The screen resolution is 1280x1024.
            """

            messages = [{"role": "user", "content": "Start the design process now."}]

            # Run for 15 turns or until success
            for i in range(15):
                # Take screenshot for Claude
                screenshot_path = f"claudes_view.png"
                await page.screenshot(path=screenshot_path)
                
                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                # Call Claude Computer Use
                response = client.beta.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Iteration {i}: What is your next move?"},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}}
                        ]
                    }],
                    betas=["computer-use-2024-10-22"]
                )

                # Process Claude's decision
                for content in response.content:
                    if content.type == "tool_use" and content.name == "computer":
                        action = content.input["action"]
                        coords = content.input.get("coordinate")
                        text = content.input.get("text")

                        print(f"CLAUDE ACTION: {action} at {coords}")
                        
                        # Execute Claude's action via Playwright
                        if action == "mouse_move":
                            await page.mouse.move(coords[0], coords[1])
                        elif action == "left_click":
                            await page.mouse.click(coords[0], coords[1])
                        elif action == "type":
                            await page.keyboard.type(text)
                        elif action == "key":
                            await page.keyboard.press(text)

                if "Sales mode" in page.url or "e-proposal" in page.url:
                    print("LOG: Claude successfully reached Sales Mode!")
                    break
                
                await asyncio.sleep(5) # Give the UI time to react

            return page.url

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            print("LOG: Process complete. Keeping VNC alive for 5 mins.")
            await asyncio.sleep(300)
            await context.close()