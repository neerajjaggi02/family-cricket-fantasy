import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser

# --- CONFIG & SECRETS ---
API_KEY = "97efb164-e552-4332-93a8-60aaaefe0f1d" # Your provided key
SERIES_ID = "834fa251-40c0-432a-bc96-d4f13110298a" # T20 World Cup 2026 ID
SHEET_URL = st.secrets["GSHEET_URL"]

st.set_page_config(page_title="World Cup Fantasy Tracker", page_icon="🏏", layout="wide")

# --- SIDEBAR: RULES ---
with st.sidebar:
    st.title("🏆 Series Rules")
    st.markdown("🧤 **2 WK** | 🏏 **Max 6 Bat**\n\n⚡ **1 AR** | 🎾 **1 Bowl**")
    st.divider()
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS ---
@st.cache_data(ttl=600)
def get_series_data():
    """Fetches every match in the specific Series."""
    url = f"https://api.cricapi.com/v1/series_info?apikey={API_KEY}&id={SERIES_ID}"
    try:
        res = requests.get(url).json()
        if res.get("status") == "success":
            return res.get("data", {}).get("matchList", [])
    except: return []
    return []

# --- MAIN UI ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.header("🏏 T20 World Cup 2026: Full Schedule")
    all_matches = get_series_data()
    
    if all_matches:
        now = datetime.now(timezone.utc)
        
        # CATEGORIZE
        live_matches = []
        upcoming_matches = []
        completed_matches = []
        
        for m in all_matches:
            # Note: series_info uses 'date' and 'dateTimeGMT'
            m_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
            
            # Use 'status' string to help determine state
            status = m.get('status', '').lower()
            
            if "won by" in status or "abandoned" in status or "drawn" in status:
                completed_matches.append(m)
            elif now > m_time or "live" in status:
                live_matches.append(m)
            else:
                upcoming_matches.append(m)

        # 🔴 LIVE SECTION
        if live_matches:
            st.subheader("🔥 Live Now")
            for m in live_matches:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{m['name']}**")
                        st.info(f"📢 {m['status']}")
                    with col2:
                        st.code(m['id'])
                    st.divider()

        # ⏳ UPCOMING SECTION
        st.subheader("📅 Upcoming Fixtures")
        for m in upcoming_matches[:10]: # Show next 10
            m_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
            ist_t = m_time + timedelta(hours=5, minutes=30)
            diff = m_time - now
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"**{m['name']}**")
                    st.caption(f"🕒 {ist_t.strftime('%d %b, %I:%M %p')} IST")
                with c2:
                    h, rem = divmod(int(diff.total_seconds()), 3600)
                    m_left, _ = divmod(rem, 60)
                    st.warning(f"⏳ {h}h {m_left}m left")
                with c3:
                    st.write("ID:")
                    st.code(m['id'])
                st.divider()

        # 🏁 COMPLETED SECTION
        with st.expander("✅ View Recently Completed Matches"):
            for m in reversed(completed_matches[-15:]): # Show last 15
                st.write(f"**{m['name']}**")
                st.success(m['status'])
                st.caption(f"Match ID: `{m['id']}`")
                st.divider()
    else:
        st.error("No matches found for this Series ID. Please check your API credits.")
