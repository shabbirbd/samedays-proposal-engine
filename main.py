from fastapi import FastAPI, BackgroundTasks
from agent_logic import run_aurora_automation
import uvicorn

app = FastAPI()

@app.post("/trigger-proposal")
async def trigger(data: dict, background_tasks: BackgroundTasks):
    rep_id = data.get("rep_id", "rep_1")
    customer = data.get("customer_name")
    
    background_tasks.add_task(start_agent, rep_id, customer)
    return {"status": "accepted", "message": f"Robot is searching for {customer}..."}

async def start_agent(rep_id, customer):
    try:
        result = await run_aurora_automation(rep_id, customer)
        print(f"AGENT RESULT: {result}")
    except Exception as e:
        print(f"SYSTEM ERROR: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)