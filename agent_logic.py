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
    print(f"LOG: Starting High-Precision Agent for {customer_name}")
    
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
            # --- PHASE 1: LOGIN & NAVIGATE (Playwright) ---
            print("LOG: Navigating to Aurora...")
            await page.goto("https://v2.aurorasolar.com/projects", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            if "login" in page.url:
                await page.get_by_label("Email").fill(os.getenv("AURORA_EMAIL"))
                await page.get_by_label("Password").fill(os.getenv("AURORA_PASSWORD"))
                await page.get_by_role("button", name="Log in").click()
                await page.wait_for_url("**/projects", timeout=120000)
            
            search = page.locator("input[placeholder*='Search']").first
            await search.fill(customer_name)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)
            await page.get_by_text(customer_name, exact=False).first.click()
            await asyncio.sleep(5)
            
            print("LOG: Clicking New Design button...")
            await page.get_by_role("button", name="New design").click()
            await asyncio.sleep(40) 

            # Dismiss "Restore" popup if present
            try:
                await page.get_by_role("button", name="Restore").click(timeout=3000)
            except: pass

            # --- PHASE 2: THE VISION LOOP (Claude Sonnet 4.6) ---
            system_prompt = f"""
            You are a solar design expert. Resolution: 1280x1024.
            Goal: Proposal for {customer_name}. 

            PRECISION RULES:
            1. TOASTS: Look at the BOTTOM CENTER of the screen for notifications (e.g. 'AI SmartRoof complete' or 'AutoDesigner completed'). Do NOT proceed to the next phase until the toast confirms the current one is done.
            2. SCROLLING: The right-hand sidebar for AutoDesigner is long. If you cannot see 'Microinverters', you MUST scroll down. Use ACTION: SCROLL(500).
            3. HARDWARE: 
               - Select Panels starting with 'GL_'.
               - Select Microinverters starting with 'GL_'.
            4. FINANCE: Once panels are on the roof and toast confirms completion, click the Dollar icon (Top Center).
               - Select 'GoodLeap' -> WAIT(5) -> Select 'GoodLeap Lease Solar only 2.99% ESC'.
               - Finish with 'Save' and 'Sales mode'.

            COMMAND FORMAT:
            Respond with one action:
            ACTION: CLICK(x, y)
            ACTION: TYPE("text")
            ACTION: WAIT(5)
            ACTION: SCROLL(500)  <-- Use this to see microinverters in the sidebar
            """

            messages = []
            for iteration in range(60):
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
                            {"type": "text", "text": f"Current URL: {page.url}. What is the next action? Check bottom center for toasts."}
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
                scroll_match = re.search(r"ACTION: SCROLL\((\d+)\)", thought)

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
                elif scroll_match:
                    amount = int(scroll_match.group(1))
                    print(f"EXECUTING: Scroll sidebar by {amount}")
                    # Move mouse to the sidebar area first then scroll
                    await page.mouse.move(1100, 500) 
                    await page.mouse.wheel(0, amount)

                if "e-proposal" in page.url:
                    print(f"LOG: SUCCESS! Final URL: {page.url}")
                    return page.url

            return "FAILED: Max iterations"

        except Exception as e:
            print(f"!!! AGENT ERROR: {e}")
            return f"ERROR: {e}"
        finally:
            print("LOG: Process complete. VNC remains open for review.")
            await asyncio.sleep(300)
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_aurora_automation("rep_1", "Test Testcase"))