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
    print(f"LOG: Starting Full OpenClaw Agent for {customer_name}")
    
    async with async_playwright() as p:
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        # Launch browser on virtual display :99
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
            # Step 1: Open the browser to the starting point
            print("LOG: Opening Aurora...")
            await page.goto("https://v2.aurorasolar.com/projects")
            
            # THE COMPUTER USE LOOP
            # We give Claude a list of objectives. He decides which tool to use.
            
            system_prompt = f"""
            You are a solar design expert using a computer. 
            The screen resolution is 1280x1024.
            
            Your ultimate goal: Create a Sales Mode proposal for the customer: {customer_name}
            
            Follow these steps visually:
            1. LOGIN: If you see a login screen, type the email '{os.getenv("AURORA_EMAIL")}' and password '{os.getenv("AURORA_PASSWORD")}'. If MFA appears, type 'WAITING FOR MFA' in the logs and wait.
            2. SEARCH: Locate the search bar on the projects page. Type '{customer_name}' and press Enter.
            3. OPEN: Click on the customer '{customer_name}' when it appears in the list.
            4. DESIGN: Click the '+ New Design' button. 
            5. CAD LOAD: If a 'Coming right up' or loading screen appears, wait for the 3D map to show.
            6. ROOF: Click the 'Roof' icon in the sidebar, then click 'AI SmartRoof'. Wait for it to finish.
            7. SYSTEM: Click the 'System' tab, then 'AutoDesigner', then 'Run AutoDesigner'.
            8. ERROR FIX: If a red error says 'Inverter required', click 'Components', pick any inverter, and run AutoDesigner again.
            9. FINISH: Click 'Sales Mode' in the top right.
            
            Once you see a URL containing 'e-proposal', you have succeeded.
            """

            messages = []
            
            # We allow up to 30 "thoughts" (steps) to complete the whole job
            for iteration in range(30):
                # 1. Take Screenshot
                screenshot_path = f"agent_view.png"
                await page.screenshot(path=screenshot_path)
                
                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                # 2. Ask Claude what to do
                response = client.beta.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Current URL: {page.url}. What is your next move to reach the goal?"},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}}
                        ]
                    }],
                    betas=["computer-use-2024-10-22"]
                )

                # Add Claude's thought to the history
                messages.append({"role": "user", "content": f"Step {iteration} analysis requested."})
                
                # 3. Execute Claude's tool calls
                for content in response.content:
                    if content.type == "text":
                        print(f"CLAUDE THOUGHT: {content.text}")
                    
                    if content.type == "tool_use" and content.name == "computer":
                        action = content.input["action"]
                        coords = content.input.get("coordinate")
                        text = content.input.get("text")

                        print(f"ACTION: {action} | Coords: {coords} | Text: {text}")

                        if action == "mouse_move":
                            await page.mouse.move(coords[0], coords[1])
                        elif action == "left_click":
                            await page.mouse.click(coords[0], coords[1])
                        elif action == "type":
                            await page.keyboard.type(text)
                        elif action == "key":
                            await page.keyboard.press(text)
                        elif action == "wait":
                            await asyncio.sleep(5)

                # 4. Check if we reached the goal
                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! Goal reached at {page.url}")
                    return page.url
                
                await asyncio.sleep(2) # Breathing room between steps

            return "FAILED: Max iterations reached."

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            print("LOG: Cleaning up. Keeping VNC open for 5 mins.")
            await asyncio.sleep(300)
            await context.close()