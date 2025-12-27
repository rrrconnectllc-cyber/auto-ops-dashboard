# Note: Install azure-identity with: pip install azure-identity
# Or install all requirements: pip install -r requirements.txt
import os
import requests
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv

# 1. Load Secrets
load_dotenv()

def check_intune():
    print("☁️  Connecting to Microsoft Graph (Direct Mode)...")
    
    try:
        # 2. Get the Access Token (The "Badge")
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
        
        # Request a token specifically for the Graph API
        print("🔑 Authenticating...")
        token = credential.get_token("https://graph.microsoft.com/.default")
        
        # 3. Call the API
        endpoint = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices"
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        print("📡 Scanning for devices...")
        response = requests.get(endpoint, headers=headers)
        
        if response.status_code == 200:
            devices = response.json().get('value', [])
            print(f"✅ Success! Connected to your Azure Tenant.")
            print(f"📱 Found {len(devices)} devices enrolled in Intune.")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"⚠️  Details: {response.text}")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    check_intune()