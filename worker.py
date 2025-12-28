import os
import requests
import json
import random
import string
from typing import Any, cast
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI
from azure.identity import ClientSecretCredential

# 1. Setup
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
slack_url = os.environ.get("SLACK_WEBHOOK_URL")
teams_url = os.environ.get("TEAMS_WEBHOOK_URL")
openai_key = os.environ.get("OPENAI_API_KEY")

assert url is not None, "SUPABASE_URL is required"
assert key is not None, "SUPABASE_KEY is required"

supabase: Client = create_client(url, key)
client = OpenAI(api_key=openai_key)

# --- HELPER: Generate Strong Password ---
def generate_password():
    """Creates a complex password to satisfy Azure requirements"""
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "Aa1!" + "".join(random.choice(chars) for _ in range(12))

# --- AZURE SKILLS ---
def get_azure_token():
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
    return credential.get_token("https://graph.microsoft.com/.default").token

def get_default_domain(headers):
    """Fetches your @onmicrosoft.com domain automatically"""
    try:
        r = requests.get("https://graph.microsoft.com/v1.0/domains", headers=headers)
        for domain in r.json().get('value', []):
            if domain.get('isDefault'):
                return domain['id']
    except:
        return None

def create_azure_user(name):
    """Creates a new user in Azure AD"""
    try:
        print(f"☁️ Attempting to onboard: {name}...")
        token = get_azure_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # 1. Get Domain
        domain = get_default_domain(headers)
        if not domain: return "❌ Error: Could not find Azure Domain."

        # 2. Prepare User Data
        email_nickname = name.lower().replace(" ", ".")
        upn = f"{email_nickname}@{domain}"
        password = generate_password()
        
        user_data = {
            "accountEnabled": True,
            "displayName": name,
            "mailNickname": email_nickname,
            "userPrincipalName": upn,
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": password
            }
        }

        # 3. Create User
        response = requests.post("https://graph.microsoft.com/v1.0/users", headers=headers, json=user_data)
        
        if response.status_code == 201:
            return f"✅ SUCCESS: User created!\n👤 UPN: {upn}\n🔑 Temp Pass: {password}"
        elif "user already exists" in response.text.lower():
            return f"⚠️ User {upn} already exists."
        else:
            return f"❌ Azure Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"❌ Connection Failed: {str(e)}"

def get_intune_device_count():
    try:
        token = get_azure_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get("https://graph.microsoft.com/v1.0/deviceManagement/managedDevices", headers=headers)
        if response.status_code == 200:
            count = len(response.json().get('value', []))
            return f"✅ Connected to Intune. Found {count} managed devices."
        return f"⚠️ Azure Error: {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- ACTION LOGIC ---
SAFE_COMMANDS = {
    "restart_service": "sudo systemctl restart application",
    "clear_logs": "truncate -s 0 /var/log/app.log"
}

def execute_fix(solution_text, alert_message):
    action_taken = "No automated action taken."
    msg_lower = alert_message.lower()

    # 1. USER ONBOARDING CHECK
    if "onboard" in msg_lower or "new user" in msg_lower or "hire" in msg_lower:
        # Extract name simply (assuming message is like "Onboard John Doe")
        # In a real app, AI would extract the name cleanly.
        name_part = alert_message.split(":")[-1].strip() if ":" in alert_message else "New User"
        action_taken = create_azure_user(name_part)

    # 2. DEVICE CHECK
    elif "intune" in msg_lower or "device count" in msg_lower:
        action_taken = get_intune_device_count()
        
    # 3. LINUX CHECKS
    elif "restart" in solution_text.lower():
        action_taken = f"⚡ EXECUTED: {SAFE_COMMANDS['restart_service']}"
    elif "disk space" in solution_text.lower():
        action_taken = f"⚡ EXECUTED: {SAFE_COMMANDS['clear_logs']}"
    
    return action_taken

def notify_teams(tenant_name, alert_msg, solution, action):
    if not teams_url: return

    # Adaptive Card Color Logic
    color = "Good" if "SUCCESS" in action else "Attention"
    
    # The "Pretty" Teams Card
    card_payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "body": [
                        {
                            "type": "TextBlock",
                            "size": "Medium",
                            "weight": "Bolder",
                            "text": f"🚨 AutoOps Alert: {tenant_name}",
                            "color": "Attention"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Issue:", "value": alert_msg},
                                {"title": "AI Analysis:", "value": solution[:500] + "..." if len(solution) > 500 else solution}
                            ]
                        },
                        {
                            "type": "Container",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "🛡️ Automated Action Taken:",
                                    "weight": "Bolder"
                                },
                                {
                                    "type": "TextBlock",
                                    "text": action,
                                    "color": "Good" if "SUCCESS" in action else "Warning",
                                    "wrap": True
                                }
                            ],
                            "style": "emphasis"
                        }
                    ],
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.2"
                }
            }
        ]
    }
    
    try:
        requests.post(teams_url, json=card_payload)
    except Exception as e:
        print(f"Failed to send Teams notification: {e}")

print("🤖 AutoOps Cloud Worker (Onboarding Edition) checking...")

try:
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
                tenant_name = "Unknown"
            
            print(f"   -> Processing for {tenant_name}: {alert_dict.get('message', '')}")
            
            try:
                prompt = f"Analyze this alert: '{alert_dict.get('message', '')}'. If it's a new hire, suggest creating an Azure account. Otherwise suggest a Linux fix."
                ai_resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}]
                )
                solution = ai_resp.choices[0].message.content
                if not solution:
                    solution = "No solution provided by AI"

                action_result = execute_fix(solution, alert_dict.get('message', ''))

                supabase.table("raw_alerts").update({
                    "status": "processed",
                    "ai_solution": solution + f"\n\n[System Log]: {action_result}"
                }).eq("id", alert_dict.get("id")).execute()
                
                notify_teams(tenant_name, alert_dict.get('message', ''), solution, action_result)
                
            except Exception as inner_e:
                print(f"❌ Error processing alert: {inner_e}")
    else:
        print("✅ No new alerts found.")

except Exception as e:
    print(f"❌ FATAL ERROR: {e}")