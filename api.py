import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. Setup
load_dotenv()
url: str | None = os.environ.get("SUPABASE_URL")
key: str | None = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Missing required environment variables: SUPABASE_URL and/or SUPABASE_KEY")

assert url is not None and key is not None  # Type narrowing for type checker
supabase: Client = create_client(url, key)

app = FastAPI(title="AutoOps Universal Listener")

# 2. Define the expected data format (The Contract)
# Any tool sending us data MUST provide at least a source and message.
class AlertPayload(BaseModel):
    source: str
    message: str
    severity: str = "Critical"  # Default to Critical if not specified

# 3. The "Door" (Webhook Endpoint)
@app.post("/webhook")
async def receive_alert(alert: AlertPayload):
    print(f"📥 Received alert from {alert.source}: {alert.message}")
    
    try:
        # Insert into Database
        data = {
            "source": alert.source,
            "message": alert.message,
            "severity": alert.severity,
            "status": "new"  # This triggers your AI Worker!
        }
        response = supabase.table("raw_alerts").insert(data).execute()
        
        return {"status": "success", "msg": "Alert queued for AI Agent"}
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "AutoOps Listener is Online"}