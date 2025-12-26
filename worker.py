import os
import requests
import json
from typing import cast, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# 1. Setup
load_dotenv()
url: str | None = os.environ.get("SUPABASE_URL")
key: str | None = os.environ.get("SUPABASE_KEY")
openai_key: str | None = os.environ.get("OPENAI_API_KEY")
slack_url = os.environ.get("SLACK_WEBHOOK_URL")

if not url or not key or not openai_key:
    raise ValueError("Missing required environment variables: SUPABASE_URL, SUPABASE_KEY, and/or OPENAI_API_KEY")

# Type narrowing: after validation, these are guaranteed to be str
supabase_url: str = cast(str, url)
supabase_key: str = cast(str, key)
openai_api_key: str = cast(str, openai_key)

supabase: Client = create_client(supabase_url, supabase_key)
client = OpenAI(api_key=openai_api_key)

# 2. Define "Safe" Actions the Bot can take
SAFE_COMMANDS = {
    "restart_service": "sudo systemctl restart application",
    "clear_logs": "truncate -s 0 /var/log/app.log",
    "clear_cache": "redis-cli FLUSHALL"
}

def execute_fix(solution_text):
    """
    Scans the AI solution to see if it suggests a known safe action.
    In a real app, this would use 'paramiko' to SSH into the server.
    """
    action_taken = "No automated action taken (Manual review required)."
    
    if "restart" in solution_text.lower():
        action_taken = f"⚡ EXECUTED: {SAFE_COMMANDS['restart_service']}"
    elif "disk space" in solution_text.lower() or "clear" in solution_text.lower():
        action_taken = f"⚡ EXECUTED: {SAFE_COMMANDS['clear_logs']}"
    
    return action_taken

def notify_slack(tenant_name, alert_msg, solution, action):
    if not slack_url: return
    
    payload = {
        "text": f"🚨 *Alert ({tenant_name}):* {alert_msg}\n"
                f"🧠 *AI Analysis:* {solution}\n"
                f"🛡️ *Auto-Fix:* {action}"
    }
    try: requests.post(slack_url, json=payload)
    except: pass

print("🤖 AutoOps Cloud Worker (v2) checking for alerts...")

try:
    # 3. Fetch alerts (Now fetching the Tenant Name too!)
    response = supabase.table("raw_alerts") \
        .select("*, tenants(name)") \
        .eq("status", "new") \
        .execute()
        
    alerts = response.data

    if alerts:
        print(f"🚨 Found {len(alerts)} new alerts!")
        
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            alert_dict: dict[str, Any] = cast(dict[str, Any], alert)
            tenants = alert_dict.get("tenants")
            tenant_name = "Unknown"
            if isinstance(tenants, dict):
                tenant_name = tenants.get("name", "Unknown")
            print(f"   -> Processing for {tenant_name}: {alert_dict['message']}")
            
            # 4. Analyze
            prompt = f"Analyze this server alert and suggest a 1-sentence Linux command to fix it: {alert_dict['message']}"
            ai_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            solution = ai_resp.choices[0].message.content
            if not solution:
                solution = "No solution provided by AI"
            
            # Type narrowing: solution is guaranteed to be str at this point
            solution_str: str = cast(str, solution)

            # 5. EXECUTE THE FIX
            action_result = execute_fix(solution_str)

            # 6. Update DB
            supabase.table("raw_alerts").update({
                "status": "processed",
                "ai_solution": solution_str + f"\n\n[System Log]: {action_result}"
            }).eq("id", alert_dict["id"]).execute()
            
            # 7. Notify
            notify_slack(tenant_name, alert_dict["message"], solution_str, action_result)
            
    else:
        print("✅ No new alerts found.")

except Exception as e:
    print(f"Error: {e}")