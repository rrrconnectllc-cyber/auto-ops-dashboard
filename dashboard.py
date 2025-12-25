import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from supabase import create_client

# 1. Setup Connection
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

# Page Config
st.set_page_config(page_title="AutoOps Dashboard", page_icon="🤖", layout="wide")
st.title("🤖 AutoOps Command Center")

# 2. Fetch Data from Supabase
# We sort by created_at descending so the newest alerts are at the top
response = supabase.table("raw_alerts").select("*").order("created_at", desc=True).execute()
rows = response.data

if rows:
    # Convert to a Pandas DataFrame for easy display
    df = pd.DataFrame(rows)

    # 3. Top Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    
    total_alerts = len(df)
    critical_alerts = len(df[df['severity'] == 'Critical'])
    processed = len(df[df['status'] == 'processed'])
    pending = len(df[df['status'] == 'new'])

    col1.metric("Total Alerts", total_alerts)
    col2.metric("Critical", critical_alerts, delta_color="inverse")
    col3.metric("AI Solved", processed, delta_color="normal")
    col4.metric("Pending", pending)

    st.divider()

    # 4. Main Data Table
    st.subheader("📋 Live Alert Feed")
    # Show specific columns to keep it clean
    display_df = df[['id', 'created_at', 'source', 'severity', 'message', 'status']]
    st.dataframe(display_df, width=1000)

    # 5. Detail Inspector
    st.divider()
    st.subheader("🔍 Solution Inspector")
    
    # Dropdown to select an alert
    selected_id = st.selectbox("Select an Alert ID to view AI Analysis:", df['id'])
    
    if selected_id:
        # Get the specific row
        row = df[df['id'] == selected_id].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.info(f"**Source:** {row['source']}")
            st.warning(f"**Issue:** {row['message']}")
            st.text(f"Status: {row['status']}")
            
        with c2:
            st.success("**AI Recommended Solution:**")
            st.markdown(row['ai_solution'] if row['ai_solution'] else "*Waiting for analysis...*")

else:
    st.info("No alerts found in the database yet. Waiting for input...")

# Manual Refresh Button
if st.button("🔄 Refresh Data"):
    st.rerun()