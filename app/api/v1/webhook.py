from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from app.core.database import supabase

router = APIRouter()

class AlertPayload(BaseModel):
    source: str
    severity: str
    message: str
    metadata: Dict[str, Any] | None = None

@router.post("/webhook/ingest")
async def ingest_alert(payload: AlertPayload):
    """
    Receives an alert from Datadog/Azure/etc. and saves it to Supabase.
    """
    try:
        data = payload.model_dump()
        
        # Insert into Supabase 'raw_alerts' table
        response = supabase.table("raw_alerts").insert(data).execute()
        
        return {"status": "received", "id": response.data[0]['id']}
        
    except Exception as e:
        # In real life, log this error properly
        raise HTTPException(status_code=500, detail=str(e))
