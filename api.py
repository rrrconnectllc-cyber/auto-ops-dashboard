import os
from fastapi import FastAPI, HTTPException, Header, Depends
from typing import Optional, cast
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. Setup
load_dotenv()
url: str | None = os.environ.get("SUPABASE_URL")
key: str | None = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Missing required environment variables: SUPABASE_URL and/or SUPABASE_KEY")

# Type narrowing: after validation, url and key are guaranteed to be str
supabase: Client = create_client(cast(str, url), cast(str, key))

app = FastAPI(title="AutoOps Multi-Tenant API")

# 2. Define expected data
class AlertPayload(BaseModel):
    source: str
    message: str
    severity: str = "Critical"

# 3. Security Check Function
async def get_tenant(x_api_key: Optional[str] = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    
    # Check DB for this key
    response = supabase.table("tenants").select("id", "name").eq("api_key", x_api_key).execute()
    
    if not response.data:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    return response.data[0] # Return the tenant info (id, name)

# 4. The Secure Webhook
@app.post("/webhook")
async def receive_alert(alert: AlertPayload, tenant: dict = Depends(get_tenant)):
    print(f"📥 Alert from {tenant['name']}: {alert.message}")
    
    try:
        data = {
            "tenant_id": tenant["id"],  # Link alert to the specific customer
            "source": alert.source,
            "message": alert.message,
            "severity": alert.severity,
            "status": "new"
        }
        supabase.table("raw_alerts").insert(data).execute()
        return {"status": "success", "msg": f"Alert queued for {tenant['name']}"}
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "AutoOps Secure API Online"}