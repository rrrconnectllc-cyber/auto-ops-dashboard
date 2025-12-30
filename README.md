# 🤖 AutoOps: AI-Powered Autonomous IT Engineer

**AutoOps** is a multi-tenant SaaS platform that automates IT operations using **OpenAI GPT-4**. It listens for alerts, analyzes the root cause, and autonomously executes fixes across **Azure Cloud** (Identity, VMs, Intune) and **Linux Servers**.

![Status](https://img.shields.io/badge/Status-Production-green) ![Stack](https://img.shields.io/badge/Tech-Python%20%7C%20Azure%20%7C%20OpenAI%20%7C%20Stripe-blue)

---

## 🚀 Features

### 🧠 1. AI-Driven Incident Response
* **Intelligent Analysis:** GPT-4 analyzes raw alert logs to determine the root cause (e.g., distinguishing between a "frozen server" and a "slow database").
* **Dual-Channel Broadcasting:** Automatically formats and broadcasts alerts to **Microsoft Teams** (Adaptive Cards) and **Slack**.
* **Safety Limits:** Intelligent text truncation to prevent message size errors on Teams.

### ☁️ 2. Azure Cloud Automation
* **Auto-Onboarding:** Detects "New Hire" tickets and automatically creates **Azure AD Users** via Graph API.
* **Infrastructure Healing:** Detects unresponsive VMs and triggers **Instant Restarts** via Azure Management API.
* **Security Auditing:** Queries **Microsoft Intune** to report on unmanaged devices and compliance status.

### 🐧 3. Server Management
* **Disk Auto-Cleanup:** Automatically clears log files (`/var/log`) when disk usage exceeds critical thresholds.
* **Service Recovery:** Restarts crashed Linux services (`systemctl`) based on AI recommendations.

### 💰 4. Built-in Monetization (SaaS)
* **Stripe Integration:** Fully automated payment portal.
* **Auto-Provisioning:** Users pay $29/mo via Stripe, and the system automatically generates and emails a unique `x-api-key` for secure access.

---

## 🛠️ Architecture

**The Flow:**
1.  **Trigger:** Client sends a JSON alert via Webhook (from SolarWinds, Datadog, or Curl).
2.  **Auth:** `api.py` verifies the Customer API Key.
3.  **Queue:** Alert is stored in **Supabase** (PostgreSQL) as "New".
4.  **Worker:** `worker.py` picks up the alert.
5.  **Brain:** OpenAI GPT-4 decides the fix.
6.  **Hands:** Python executes the fix (Azure Graph API, Azure Mgmt API, or SSH).
7.  **Voice:** Updates are pushed to Teams & Slack.

---

## ⚙️ Tech Stack

* **Backend:** Python 3.10, FastAPI
* **Database:** Supabase (PostgreSQL)
* **AI Engine:** OpenAI GPT-4o
* **Cloud Provider:** Render (Hosting), Microsoft Azure (Target)
* **Payments:** Stripe (Live Mode)
* **Notifications:** Microsoft Teams (Adaptive Cards 1.4), Slack Webhooks

---

## 🔐 Environment Variables

To run this project, you need the following keys in your `.env` file or Render Environment:

| Variable | Description |
| :--- | :--- |
| `SUPABASE_URL` | Connection URL for the database |
| `SUPABASE_KEY` | Service Role Key for Supabase |
| `OPENAI_API_KEY` | Key for GPT-4 analysis |
| `TEAMS_WEBHOOK_URL` | URL for Microsoft Teams Workflow |
| `SLACK_WEBHOOK_URL` | URL for Slack App Webhook |
| `AZURE_CLIENT_ID` | App Registration Client ID |
| `AZURE_CLIENT_SECRET` | App Registration Client Secret |
| `AZURE_TENANT_ID` | Microsoft Entra Tenant ID |
| `AZURE_SUBSCRIPTION_ID`| **Critical:** The Subscription ID where VMs live |
| `STRIPE_SECRET_KEY` | Stripe Live/Test Secret Key (`sk_...`) |
| `STRIPE_WEBHOOK_SECRET`| Stripe Signing Secret (`whsec_...`) |

---

## ⚡ Quick Start (How to Trigger)

### 1. Test Azure VM Restart (Infrastructure)
*Triggers an immediate reboot of the production server.*
```bash
curl -X POST "[https://auto-ops-dashboard.onrender.com/webhook](https://auto-ops-dashboard.onrender.com/webhook)" \
     -H "Content-Type: application/json" \
     -H "x-api-key: YOUR_API_KEY" \
     -d '{"source": "Azure Monitor", "message": "Critical: Production-VM is unresponsive and frozen. Immediate restart required.", "severity": "Critical"}'






