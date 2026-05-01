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
    # Ensure display is set for the server environment
    os.environ["DISPLAY"] = ":99"
    
    print(f"LOG: Starting Agent for {customer_name} using Claude Sonnet 4.6")
    
    async with async_playwright() as p:
        profile_path = f"/home/ubuntu/samedays-proposal-engine/profiles/{rep_id}"
        
        # Launch browser with stability flags
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
            # Step 1: Open Aurora
            print("LOG: Navigating to Aurora Projects...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(8)

            system_prompt = f"""
            You are a solar design assistant. Screen resolution: 1280x1024.
            Goal: Create a proposal for customer: {customer_name}
            
            1. If Login screen appears: Type email '{os.getenv("AURORA_EMAIL")}' and password '{os.getenv("AURORA_PASSWORD")}'.
            2. If MFA appears: Pause and tell the user to enter code in VNC.
            3. On Projects page: Type '{customer_name}' in search, press Enter, click the customer.
            4. In Project: Click '+ New Design'. 
            5. In Designer: Click 'Roof' menu -> 'AI SmartRoof'. Wait for it to finish.
            6. Run AutoDesigner: Click 'System' tab -> 'AutoDesigner' -> 'Run'.
            7. Finish: Click 'Sales mode'. 
            """

            messages = []
            
            for iteration in range(25):
                print(f"LOG: Iteration {iteration} - Analyzing Screen...")
                await asyncio.sleep(2) 
                
                try:
                    screenshot_path = f"agent_view.png"
                    await page.screenshot(path=screenshot_path, animations="disabled")
                except Exception as e:
                    print(f"LOG: Screenshot failed, retrying... {e}")
                    continue

                with open(screenshot_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")

                # Using the model ID 'claude-sonnet-4-6' which your key has access to
                response = client.beta.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages + [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Current URL: {page.url}. Next step?"},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}}
                        ]
                    }],
                    betas=["computer-use-2024-10-22"]
                )

                messages.append({"role": "user", "content": f"Step {iteration} analysis requested."})
                
                for content in response.content:
                    if content.type == "text":
                        print(f"CLAUDE THOUGHT: {content.text}")
                    
                    if content.type == "tool_use" and content.name == "computer":
                        action = content.input["action"]
                        coords = content.input.get("coordinate")
                        text = content.input.get("text")

                        print(f"ACTION: {action} | {coords if coords else text}")

                        if action == "mouse_move":
                            await page.mouse.move(coords[0], coords[1])
                        elif action == "left_click":
                            await page.mouse.click(coords[0], coords[1])
                        elif action == "type":
                            await page.keyboard.type(text, delay=50)
                        elif action == "key":
                            await page.keyboard.press(text)

                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! Link: {page.url}")
                    return page.url
                
                await asyncio.sleep(2)

            return "FAILED: Max iterations"

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            print("LOG: Cleaning up. VNC remains open for 5 mins.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))