import requests

# PASTE YOUR LONG TEAMS URL INSIDE THE QUOTES
teams_url = "https://defaultb4b2926cbb0c43b0b94552ae7d78c6.f6.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/a17a9389861e40d9a22df19cdb5d112f/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=Payfiw9l1rVe5PB_TZBZ8dGnb2LSMU3Vk3iw1FvUMyo" 

payload = {
    "type": "message",
    "attachments": [
        {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "type": "AdaptiveCard",
                "body": [
                    {"type": "TextBlock", "text": "🔔 This is a Test Ping from AutoOps", "size": "Large"}
                ],
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "version": "1.2"
            }
        }
    ]
}

print(f"🚀 Sending to: {teams_url[:30]}...")
try:
    r = requests.post(teams_url, json=payload)
    print(f"✅ Status Code: {r.status_code}")
    print(f"📄 Response: {r.text}")
except Exception as e:
    print(f"❌ Error: {e}")