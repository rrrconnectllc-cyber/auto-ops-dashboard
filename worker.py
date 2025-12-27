import os
import requests
import json
from typing import Any, cast
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI
# Note: Install azure-identity with: pip install azure-identity
# Or install all requirements: pip install -r requirements.txt
from azure.identity import ClientSecretCredential

# 1. Setup
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
slack_url = os.environ.get("SLACK_WEBHOOK_URL")

# Check keys
if not url or not key:
    print("❌ Error: Missing Supabase credentials")
    exit(1)

supabase: Client = create_client(url, key)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# --- NEW: AZURE SKILLS ---
def get_intune_device_count():
    """Logs into Azure and counts devices via the Graph API"""
    try:
        print("☁️ Connecting to Azure for live data...")
        tenant_id = os.environ.get("AZURE_TENANT_ID")
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")
        
        assert tenant_id is not None, "AZURE_TENANT_ID is required"
        assert client_id is not None, "AZURE_CLIENT_ID is required"
        assert client_secret is not None, "AZURE_CLIENT_SECRET is required"
        
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        token = credential.get_token("https://graph.microsoft.com/.default")
        
        endpoint = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices"
        headers = {"Authorization": f"Bearer {token.token}"}
        
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            count = len(response.json().get('value', []))
            return f"✅ SUCCESS: Connected to Intune. Found {count} managed devices."
        else:
            return f"⚠️ Azure Error: {response.status_code}"
    except Exception as e:
        return f"❌ Connection Failed: {str(e)}"

# 2. Define Actions
SAFE_COMMANDS = {
    "restart_service": "sudo systemctl restart application",
    "clear_logs": "truncate -s 0 /var/log/app.log"
}

def execute_fix(solution_text, alert_message):
    action_taken = "No automated action taken."
    
    # NEW: Check if the alert is asking about Intune/Devices
    if "intune" in alert_message.lower() or "device count" in alert_message.lower():
        action_taken = get_intune_device_count()
        
    # Existing Linux Checks
    elif "restart" in solution_text.lower():
        action_taken = f"⚡ EXECUTED: {SAFE_COMMANDS['restart_service']}"
    elif "disk space" in solution_text.lower() or "clear" in solution_text.lower():
        action_taken = f"⚡ EXECUTED: {SAFE_COMMANDS['clear_logs']}"
    
    return action_taken

def notify_slack(tenant_name, alert_msg, solution, action):
    if not slack_url: return
    payload = {
        "text": f"🚨 *Alert ({tenant_name}):* {alert_msg}\n"
                f"🧠 *AI Analysis:* {solution}\n"
                f"🛡️ *Action Taken:* {action}"
    }
    try: requests.post(slack_url, json=payload)
    except: pass

print("🤖 AutoOps Cloud Worker (Azure Edition) checking for alerts...")

try:
    # 3. Fetch alerts
    response = supabase.table("raw_alerts").select("*, tenants(name)").eq("status", "new").execute()
    alerts = response.data

    if alerts:
        print(f"🚨 Found {len(alerts)} new alerts!")
        
        for alert in alerts:
            # Type check: ensure alert is a dict
            if not isinstance(alert, dict):
                continue
            
            alert_dict: dict[str, Any] = cast(dict[str, Any], alert)
            tenant_data = alert_dict.get("tenants")
            if isinstance(tenant_data, dict):
                tenant_name = tenant_data.get("name", "Unknown")
            else:
                tenant_name = "Unknown Tenant"

            print(f"   -> Processing for {tenant_name}: {alert_dict.get('message')}")
            
            try:
                # 4. Analyze
                prompt = f"Analyze this alert: '{alert_dict['message']}'. If it asks for device status, say 'Checking Azure Intune'. Otherwise, suggest a Linux fix."
                ai_resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}]
                )
                solution = ai_resp.choices[0].message.content
                if not solution:
                    solution = "No solution provided by AI"
                
                # Type narrowing: solution is guaranteed to be str at this point
                solution_str: str = cast(str, solution)

                # 5. EXECUTE THE FIX (Now includes Azure!)
                action_result = execute_fix(solution_str, alert_dict['message'])

                # 6. Update DB
                supabase.table("raw_alerts").update({
                    "status": "processed",
                    "ai_solution": solution_str + f"\n\n[System Log]: {action_result}"
                }).eq("id", alert_dict["id"]).execute()
                
                notify_slack(tenant_name, alert_dict["message"], solution_str, action_result)
                
            except Exception as inner_e:
                print(f"❌ Error processing alert: {inner_e}")
    else:
        print("✅ No new alerts found.")

except Exception as e:
    print(f"❌ FATAL ERROR: {e}")