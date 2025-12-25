import os
import requests
import json
from typing import Any, cast
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# 1. Setup
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
slack_url = os.environ.get("SLACK_WEBHOOK_URL")
openai_key = os.environ.get("OPENAI_API_KEY")

if not url or not key or not openai_key:
    raise ValueError("Required environment variables not set")

assert url is not None and key is not None and openai_key is not None
supabase: Client = create_client(url, key)
client = OpenAI(api_key=openai_key)

print("🤖 AutoOps Worker checking for alerts...")

def notify_slack(alert_msg, solution):
    if not slack_url: return
    payload = {"text": f"🚨 *Fixed:* {alert_msg}\n✅ *Solution:* {solution}"}
    try: requests.post(slack_url, json=payload)
    except: pass

# --- NO WHILE LOOP HERE ---
try:
    # 2. Fetch alerts
    response = supabase.table("raw_alerts") \
        .select("*") \
        .eq("status", "new") \
        .eq("severity", "Critical") \
        .execute()
        
    alerts = cast(list[dict[str, Any]], response.data)

    if alerts:
        print(f"🚨 Found {len(alerts)} new critical alerts!")
        
        for alert in alerts:
            print(f"   -> Analyzing: {alert['message']}")
            
            # 3. Ask AI
            prompt = f"Fix this IT alert in 1 sentence: {alert['message']}"
            ai_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            solution = ai_resp.choices[0].message.content

            # 4. Save to DB
            supabase.table("raw_alerts").update({
                "status": "processed",
                "ai_solution": solution
            }).eq("id", alert["id"]).execute()
            
            # 5. Notify
            notify_slack(alert["message"], solution)
    else:
        print("✅ No new alerts found.")

except Exception as e:
    print(f"Error: {e}")