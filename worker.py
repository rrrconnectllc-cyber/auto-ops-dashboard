import time
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

if not url or not key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
if not openai_key:
    raise ValueError("OPENAI_API_KEY must be set in environment variables")

# Type narrowing: after validation, we know these are str, not None
supabase: Client = create_client(str(url), str(key))
client = OpenAI(api_key=str(openai_key))

print("🤖 AutoOps Worker is watching for alerts... (Notifications Enabled)")

# --- The Notification Engine ---
def notify_slack(alert_msg, solution):
    if not slack_url:
        print("⚠️ No Slack URL found. Skipping notification.")
        return

    # Create a "Block Kit" message (Professional UI)
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 Critical Alert Resolved",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Issue:*\n{alert_msg}"},
                    {"type": "mrkdwn", "text": "*Status:*\n✅ Fixed"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*AI Solution Applied:*\n{solution}"
                }
            },
            {
                "type": "divider"
            }
        ]
    }
    
    try:
        requests.post(slack_url, json=payload)
        print("   📨 Notification sent to Slack.")
    except Exception as e:
        print(f"   ❌ Failed to send notification: {e}")

# --- Main Loop ---
while True:
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
                prompt = f"""
                Analyze this alert and provide a short, actionable fix (max 2 sentences).
                Alert: {alert['message']}
                Source: {alert['source']}
                """
                
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
                
                # 5. SEND NOTIFICATION
                notify_slack(alert["message"], solution)

        else:
            print(".", end="", flush=True)

        time.sleep(5)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)