from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
from pydantic import BaseModel
from openai import OpenAI
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# 1. Setup Connections
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Initialize OpenAI
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# 2. Define the input model (what the AI expects)
class Alert(BaseModel):
    source: str
    message: str
    severity: str

@app.get("/")
def read_root():
    return {"status": "AutoOps Agent Ready"}

# 3. The "Brain" Endpoint
@app.post("/analyze-alert")
def analyze_alert(alert: Alert):
    try:
        # Ask GPT-4 what to do
        prompt = f"""
        You are a Senior DevOps Engineer. 
        Analyze this critical alert and provide 3 remediation steps.
        
        Alert Source: {alert.source}
        Message: {alert.message}
        Severity: {alert.severity}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",  # or "gpt-3.5-turbo" if you prefer
            messages=[{"role": "user", "content": prompt}]
        )
        
        advice = response.choices[0].message.content
        return {"ai_analysis": advice}

    except Exception as e:
        return {"error": str(e)}