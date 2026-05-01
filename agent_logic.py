import asyncio
import os
import base64
from playwright.async_api import async_playwright
from anthropic import Anthropic
from dotenv import load_dotenv

# 1. INITIAL SETUP
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def run_aurora_automation(rep_id, customer_name):
    # Ensure the script targets the virtual monitor
    os.environ["DISPLAY"] = ":99"
    
    print(f"LOG: Starting Final Hybrid Agent for {customer_name}")
    
    async with async_playwright() as p:
        # Define persistent profile to keep sessions alive
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
            # --- PHASE 1: DETERMINISTIC NAVIGATION (PLAYWRIGHT) ---
            print("LOG: Navigating to Aurora Projects...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Handle Login if cookies expired
            if "login" in page.url:
                print("LOG: Login required. Filling form...")
                await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
                await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
                await page.get_by_role("button", name="Log in").click()
                print("LOG: [ACTION] If MFA appears, type it in RealVNC.")
                await page.wait_for_url("**/projects", timeout=120000)
            
            # Search & Open Customer
            print(f"LOG: Searching for '{customer_name}'...")
            search_input = page.locator("input[placeholder*='Search']").first
            await search_input.wait_for(state="visible")
            await search_input.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)

            print(f"LOG: Opening project: {customer_name}")
            await page.get_by_text(customer_name, exact=False).first.click()
            await asyncio.sleep(5)
            
            # Click New Design
            print("LOG: Clicking New Design button...")
            await page.get_by_role("button", name="New design").click()
            
            # CAD engine takes a long time to load 3D assets
            print("LOG: Waiting 30s for CAD Engine. Handing over to Claude...")
            await asyncio.sleep(30) 

            # --- PHASE 2: AGENTIC DESIGN LOOP (CLAUDE COMPUTER USE) ---
            
            system_prompt = f"""
            You are a solar design expert. Screen resolution: 1280x1024.
            Goal: Finish the design for customer: {customer_name}
            
            DIRECTIONS:
            1. Find 'Roof' in the sidebar and click it.
            2. Click 'AI SmartRoof'. 
            3. Wait for the modeling to finish (yellow bar at bottom).
            4. Click 'System' tab, then 'AutoDesigner', then 'Run AutoDesigner'.
            5. If a red error says 'Inverter required', click 'Components', pick any inverter, and Run again.
            6. Click 'Sales mode' in the top right to finish.
            
            Success is reached when the URL contains 'e-proposal'.
            """

            # This list maintains the conversation memory
            messages = []

            for iteration in range(25):
                print(f"LOG: --- Iteration {iteration} ---")
                
                # 1. Take a screenshot for Claude to see
                screenshot_path = f"agent_view.png"
                await page.screenshot(path=screenshot_path, animations="disabled")
                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                # 2. Add current state to history
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}},
                        {"type": "text", "text": f"Current URL: {page.url}. What is the next tool call?"}
                    ]
                })

                # 3. Call the Claude 4.6 API
                response = client.beta.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages,
                    betas=["computer-use-2024-10-22"],
                    tools=[{
                        "type": "computer_20241022",
                        "name": "computer",
                        "display_width_px": 1280,
                        "display_height_px": 1024,
                        "display_number": 1,
                    }]
                )

                # 4. Parse response and execute tools
                response_content = []
                tool_results = []

                for content in response.content:
                    if content.type == "text":
                        print(f"CLAUDE THOUGHT: {content.text}")
                        response_content.append({"type": "text", "text": content.text})
                    
                    if content.type == "tool_use":
                        response_content.append(content.model_dump())
                        
                        action = content.input.get("action")
                        coords = content.input.get("coordinate")
                        text = content.input.get("text")
                        
                        result_msg = "Success"
                        try:
                            if action == "left_click":
                                await page.mouse.click(coords[0], coords[1])
                                print(f"ACTION: Clicked at {coords}")
                            elif action == "mouse_move":
                                await page.mouse.move(coords[0], coords[1])
                            elif action == "type":
                                await page.keyboard.type(text, delay=50)
                                print(f"ACTION: Typed {text}")
                            elif action == "key":
                                await page.keyboard.press(text)
                                print(f"ACTION: Pressed {text}")
                            elif action == "screenshot":
                                result_msg = "Screenshot taken"
                        except Exception as e:
                            result_msg = f"Error: {e}"
                            print(f"LOG: Tool Error - {e}")

                        # Create result for Claude
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": result_msg
                        })

                # 5. Update history with Claude's thought and our execution result
                messages.append({"role": "assistant", "content": response_content})
                messages.append({"role": "user", "content": tool_results})

                # Check for success
                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! Final URL: {page.url}")
                    return page.url
                
                await asyncio.sleep(2)

            return "FAILED: Max iterations"

        except Exception as e:
            print(f"!!! CRITICAL AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            print("LOG: Process finished. Keeping VNC open for review.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    # Test script directly
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))