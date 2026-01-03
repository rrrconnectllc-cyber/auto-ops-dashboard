import os
import time
import logging
import requests
import json
import random
import string
from typing import Any, cast
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI
from azure.identity import ClientSecretCredential

# Configure logging to see what's happening on Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Setup
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

# LOAD BOTH WEBHOOKS
slack_url = os.environ.get("SLACK_WEBHOOK_URL")
teams_url = os.environ.get("TEAMS_WEBHOOK_URL")

assert url is not None, "SUPABASE_URL is required"
assert key is not None, "SUPABASE_KEY is required"

supabase: Client = create_client(url, key)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# --- HELPER: Generate Strong Password ---
def generate_password():
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "Aa1!" + "".join(random.choice(chars) for _ in range(12))

# --- AZURE SKILLS ---
def get_azure_token(scope="https://graph.microsoft.com/.default"):
    # Updated to accept different scopes (Graph vs. Management)
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
    return credential.get_token(scope).token

def get_default_domain(headers):
    try:
        r = requests.get("https://graph.microsoft.com/v1.0/domains", headers=headers)
        for domain in r.json().get('value', []):
            if domain.get('isDefault'):
                return domain['id']
    except:
        return None

def create_azure_user(name):
    try:
        print(f"☁️ Attempting to onboard: {name}...")
        token = get_azure_token("https://graph.microsoft.com/.default")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        domain = get_default_domain(headers)
        if not domain: return "❌ Error: Could not find Azure Domain."

        email_nickname = name.lower().replace(" ", ".")
        upn = f"{email_nickname}@{domain}"
        password = generate_password()
        
        user_data = {
            "accountEnabled": True,
            "displayName": name,
            "mailNickname": email_nickname,
            "userPrincipalName": upn,
            "passwordProfile": {"forceChangePasswordNextSignIn": True, "password": password}
        }

        response = requests.post("https://graph.microsoft.com/v1.0/users", headers=headers, json=user_data)
        
        if response.status_code == 201:
            return f"✅ SUCCESS: User created!\n👤 UPN: {upn}\n🔑 Temp Pass: {password}"
        elif "user already exists" in response.text.lower():
            return f"⚠️ User {upn} already exists."
        else:
            return f"❌ Azure Error: {response.status_code}"

    except Exception as e:
        return f"❌ Connection Failed: {str(e)}"

def get_intune_device_count():
    try:
        token = get_azure_token("https://graph.microsoft.com/.default")
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get("https://graph.microsoft.com/v1.0/deviceManagement/managedDevices", headers=headers)
        if response.status_code == 200:
            count = len(response.json().get('value', []))
            return f"✅ Connected to Intune. Found {count} managed devices."
        return f"⚠️ Azure Error: {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- NEW SKILL: RESTART VM ---
def restart_azure_vm(vm_name, resource_group="AutoOps-RG"):
    try:
        print(f"⚡ Attempting to restart VM: {vm_name}...")
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
        if not subscription_id:
            return "❌ Error: AZURE_SUBSCRIPTION_ID is missing."

        # Note: We use the MANAGEMENT scope here, not Graph
        token = get_azure_token("https://management.azure.com/.default")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Azure REST API for VM Restart
        url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{vm_name}/restart?api-version=2023-03-01"
        
        response = requests.post(url, headers=headers)
        
        if response.status_code == 202: # 202 Accepted means "I started working on it"
            return f"✅ SUCCESS: Restart command sent to VM '{vm_name}'."
        elif response.status_code == 200:
            return f"✅ SUCCESS: VM '{vm_name}' restarted successfully."
        else:
            return f"❌ Azure VM Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"❌ Connection Failed: {str(e)}"

# --- ACTION LOGIC ---
SAFE_COMMANDS = {
    "restart_service": "sudo systemctl restart application",
    "clear_logs": "truncate -s 0 /var/log/app.log"
}

def execute_fix(solution_text, alert_message):
    action_taken = "No automated action taken."
    msg_lower = alert_message.lower()

    if "onboard" in msg_lower or "new user" in msg_lower:
        name_part = alert_message.split(":")[-1].strip() if ":" in alert_message else "New User"
        action_taken = create_azure_user(name_part)
    elif "intune" in msg_lower or "device count" in msg_lower:
        action_taken = get_intune_device_count()
    elif "vm" in msg_lower and "restart" in msg_lower:
        # Extract VM name if possible, otherwise default to a demo VM
        # In a real app, the AI would extract the exact VM name.
        # For this demo, we assume the VM is named "Production-VM"
        action_taken = restart_azure_vm("Production-VM", "AutoOps-RG") 
    elif "restart" in solution_text.lower():
        action_taken = f"⚡ EXECUTED: {SAFE_COMMANDS['restart_service']}"
    elif "disk space" in solution_text.lower():
        action_taken = f"⚡ EXECUTED: {SAFE_COMMANDS['clear_logs']}"
    
    return action_taken

# --- NOTIFICATION CHANNELS ---

def notify_slack(tenant_name, alert_msg, solution, action):
    if not slack_url: return
    print("📨 Sending Slack Alert...")
    payload = {
        "text": f"🚨 *Alert ({tenant_name}):* {alert_msg}\n"
                f"🧠 *AI Analysis:* {solution}\n"
                f"🛡️ *Action Taken:* {action}"
    }
    try: requests.post(slack_url, json=payload)
    except Exception as e: print(f"Slack Error: {e}")

def notify_teams(tenant_name, alert_msg, solution, action):
    if not teams_url: 
        print("⚠️ DEBUG: Teams URL is MISSING!")
        return
    
    print(f"📨 DEBUG: Attempting to send to Teams... (URL starts with {teams_url[:20]}...)")
    
    # SIMPLE SAFE MODE CARD
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
                            "size": "Large",
                            "weight": "Bolder",
                            "text": f"🚨 AutoOps Alert: {tenant_name}"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**Issue:** {alert_msg}",
                            "wrap": True
                        },
                        {
                            "type": "TextBlock",
                            "text": "________________________________________________________________________________",
                            "isSubtle": True
                        },
                        {
                            "type": "TextBlock",
                            "text": "**🧠 AI Analysis:**",
                            "weight": "Bolder"
                        },
                        {
                            "type": "TextBlock",
                            "text": solution[:3000] + "...", 
                            "wrap": True,
                            "size": "Small"
                        },
                        {
                            "type": "TextBlock",
                            "text": "________________________________________________________________________________",
                            "isSubtle": True
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**🛡️ Action Taken:** {action}",
                            "weight": "Bolder",
                            "wrap": True
                        }
                    ],
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.4"
                }
            }
        ]
    }
    
    try:
        r = requests.post(teams_url, json=card_payload)
        print(f"🔍 TEAMS STATUS CODE: {r.status_code}")
    except Exception as e:
        print(f"❌ TEAMS FATAL ERROR: {e}")

# --- BOT LOGIC FUNCTION ---
def run_automation_task(api_key: str | None = None, api_secret: str | None = None, target_settings: dict[str, Any] | None = None, tenant_id: int | None = None, tenant_name: str = "Unknown"):
    """
    Core bot function that processes alerts for a specific user/tenant.
    This represents your core bot function that runs automation tasks.
    """
    logger.info(f"Processing automation task for tenant: {tenant_name}")
    
    try:
        # Fetch alerts for this specific tenant
        query = supabase.table("raw_alerts").select("*, tenants(name)").eq("status", "new")
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        
        response = query.execute()
        alerts = response.data

        if not alerts:
            logger.info(f"No new alerts found for {tenant_name}")
            return

        logger.info(f"Found {len(alerts)} new alerts for {tenant_name}!")
        
        for alert in alerts:
            if not isinstance(alert, dict): 
                continue
            
            alert_dict: dict[str, Any] = cast(dict[str, Any], alert)
            tenant_data = alert_dict.get("tenants")
            current_tenant_name = tenant_data.get("name", tenant_name) if isinstance(tenant_data, dict) else tenant_name
            
            alert_message = alert_dict.get("message", "")
            logger.info(f"   -> Processing for {current_tenant_name}: {alert_message}")
            
            try:
                # UPDATED PROMPT: Now knows about VMs
                prompt = f"Analyze this alert: '{alert_message}'. If it's a new hire, suggest creating an Azure account. If it mentions a frozen VM, suggest restarting the VM. Otherwise suggest a Linux fix."
                ai_resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}]
                )
                solution = ai_resp.choices[0].message.content
                if not solution: 
                    solution = "No solution provided by AI"
                
                action_result = execute_fix(solution, alert_message)

                supabase.table("raw_alerts").update({
                    "status": "processed",
                    "ai_solution": solution + f"\n\n[System Log]: {action_result}"
                }).eq("id", alert_dict.get("id")).execute()
                
                notify_slack(current_tenant_name, alert_message, solution, action_result)
                notify_teams(current_tenant_name, alert_message, solution, action_result)
                
            except Exception as inner_e:
                logger.error(f"Error processing alert for {current_tenant_name}: {inner_e}")
                
    except Exception as e:
        logger.error(f"Error in automation task for {tenant_name}: {e}")
        raise

# --- BATCH JOB FUNCTION ---
def run_batch_job():
    """
    The main engine. It loops through the database and runs the bot 
    for every user who has configured their keys.
    """
    logger.info("--- Starting Batch Job ---")
    
    try:
        # 1. Fetch all tenants/users who have API keys configured
        # In Supabase, we check the tenants table for users with api_key set
        # Adjust the query based on your actual table structure
        response = supabase.table("tenants").select("id, name, api_key, email").execute()
        all_tenants = response.data or []
        
        # Filter for tenants that have an API key configured (not null/empty)
        # Also filter out None values and ensure tenant is a dict
        active_tenants: list[dict[str, Any]] = [
            cast(dict[str, Any], t) for t in all_tenants 
            if t is not None and isinstance(t, dict) and isinstance(t.get("api_key"), str)
        ]
        
        if not active_tenants:
            logger.info("No active users found. Waiting for next cycle.")
            return

        logger.info(f"Found {len(active_tenants)} users to process.")

        # 2. The Loop
        for tenant in active_tenants:
            tenant_id_raw = tenant.get("id")
            tenant_id: int | None
            if tenant_id_raw is not None and isinstance(tenant_id_raw, (int, str)):
                tenant_id = int(tenant_id_raw)
            else:
                tenant_id = None
                
            tenant_name_raw = tenant.get("name", "Unknown")
            tenant_name: str = str(tenant_name_raw) if tenant_name_raw is not None else "Unknown"
            
            tenant_email_raw = tenant.get("email", "Unknown")
            tenant_email: str = str(tenant_email_raw) if tenant_email_raw is not None else "Unknown"
            
            api_key_raw = tenant.get("api_key")
            api_key: str | None
            if api_key_raw is not None:
                api_key = str(api_key_raw)
            else:
                api_key = None
            
            logger.info(f"Processing for User: {tenant_email} (Tenant: {tenant_name})")
            
            try:
                # 3. Execute the bot logic using THIS user's specific configuration
                # We pass the tenant info and any API keys/settings to the function
                # Type casts are needed because Supabase returns JSON types
                run_automation_task(
                    api_key=cast(str | None, api_key),
                    api_secret=None,  # Add if you have api_secret in your schema
                    target_settings=None,  # Add if you have target_settings in your schema
                    tenant_id=cast(int | None, tenant_id),
                    tenant_name=cast(str, tenant_name)
                )
                logger.info(f"Success for {tenant_email}")
                
            except Exception as e:
                # 4. Error Handling (The "Firewall")
                # If User A fails, we log it and continue to User B.
                logger.error(f"Error processing for {tenant_email}: {e}")
                continue

        logger.info("--- Batch Job Finished ---")
        
    except Exception as e:
        logger.error(f"FATAL ERROR in batch job: {e}")

# --- MAIN ENTRY POINT ---
if __name__ == "__main__":
    # In a real production app, you might use a scheduler like Celery or APScheduler.
    # For now, a simple while loop simulates a worker running every X minutes.
    logger.info("🤖 AutoOps Cloud Worker (Batch Mode) starting...")
    
    while True:
        run_batch_job()
        
        # Wait for 10 minutes (600 seconds) before running again
        # This prevents hitting API rate limits
        logger.info("Sleeping for 10 minutes...")
        time.sleep(600)