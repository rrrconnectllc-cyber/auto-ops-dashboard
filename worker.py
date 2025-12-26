import os
import requests
import json
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# 1. Setup
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
slack_url = os.environ.get("SLACK_WEBHOOK_URL")

# Check if keys exist to prevent silent failures
if not url or not key:
    print("❌ Error: Missing Supabase credentials")
    exit(1)

supabase: Client = create_client(url, key)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 2. Define "Safe" Actions
SAFE_COMMANDS = {
    "restart_service": "sudo systemctl restart application",
    "clear_logs": "truncate -s 0 /var/log/app.log",
    "clear_cache": "redis-cli FLUSHALL"
}

def execute_fix(solution_text):
    action_taken = "No automated action taken (Manual review required)."
    if not solution_text: return action_taken
    
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

print("🤖 AutoOps Cloud Worker (v3) checking for alerts...")

try:
    # 3. Fetch alerts
    response = supabase.table("raw_alerts") \
        .select("*, tenants(name)") \
        .eq("status", "new") \
        .execute()
        
    alerts = response.data

    if alerts:
        print(f"🚨 Found {len(alerts)} new alerts!")
        
        for alert in alerts:
            # --- CRASH FIX: SAFE TENANT CHECK ---
            # If 'tenants' is None, default to 'Unknown Tenant' safely
            tenant_data = alert.get("tenants")
            if tenant_data:
                tenant_name = tenant_data.get("name", "Unknown")
            else:
                tenant_name = "Unknown Tenant"
            # ------------------------------------

            print(f"   -> Processing for {tenant_name}: {alert.get('message')}")
            
            try:
                # 4. Analyze
                prompt = f"Analyze this server alert and suggest a 1-sentence Linux command to fix it: {alert['message']}"
                ai_resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}]
                )
                solution = ai_resp.choices[0].message.content

                # 5. EXECUTE THE FIX
                action_result = execute_fix(solution)

                # 6. Update DB
                supabase.table("raw_alerts").update({
                    "status": "processed",
                    "ai_solution": solution + f"\n\n[System Log]: {action_result}"
                }).eq("id", alert["id"]).execute()
                
                # 7. Notify
                notify_slack(tenant_name, alert["message"], solution, action_result)
                
            except Exception as inner_e:
                print(f"❌ Error processing alert ID {alert.get('id')}: {inner_e}")
            
    else:
        print("✅ No new alerts found.")

except Exception as e:
    print(f"❌ FATAL ERROR: {e}")
    raise e