import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser

# --- CONFIG & SECRETS ---
# Using a more stable RapidAPI endpoint (Example: Cricket Live Data)
# You can get a free key from RapidAPI for "Cricket Live Score"
API_KEY = st.secrets.get("RAPID_API_KEY", "YOUR_FREE_RAPIDAPI_KEY") 
SHEET_URL = st.secrets["GSHEET_URL"]

st.set_page_config(page_title="Mumbai City Fantasy", page_icon="🏏", layout="wide")

# --- SIDEBAR: RULES & BRANDING ---
with st.sidebar:
    st.header("🏆 League Rules")
    st.markdown("""
    **Squad Rules:**
    - 🧤 **2** Wicketkeepers
    - 🏏 **Max 6** Batsmen
    - ⚡ **Min 1** All-rounder
    - 🎾 **Min 1** Bowler
    
    **Points Table:**
    - 🏃 **1 Run:** 1 pt
    - 🎾 **1 Wicket:** 25 pts
    - ⭐ **Captain:** 2.0x | **VC:** 1.5x
    """)
    if st.button("🔄 Force Refresh"):
        st.cache_data.clear()
        st.rerun()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS (Universal Fetcher) ---
@st.cache_data(ttl=300)
def fetch_all_matches():
    # Using the v1/series_info approach for the World Cup
    url = f"https://api.cricapi.com/v1/series_info?apikey={st.secrets['CRICKET_API_KEY']}&id=834fa251-40c0-432a-bc96-d4f13110298a"
    try:
        res = requests.get(url).json()
        return res.get("data", {}).get("matchList", [])
    except:
        return []

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.header("🏏 T20 World Cup 2026")
    all_matches = fetch_all_matches()
    
    if all_matches:
        now = datetime.now(timezone.utc)
        
        # CATEGORIES
        upcoming = []
        live = []
        completed = []
        
        for m in all_matches:
            m_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
            status = m.get('status', '').lower()
            
            if "won by" in status or "abandoned" in status:
                completed.append(m)
            elif m.get('matchStarted') or (now > m_time and "won" not in status):
                live.append(m)
            else:
                upcoming.append(m)

        # 1. UPCOMING SECTION
        st.subheader("📅 Upcoming Matches")
        for m in upcoming[:8]:
            m_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
            ist_t = m_time + timedelta(hours=5, minutes=30)
            diff = m_time - now
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.write(f"**{m['name']}**")
                    st.caption(f"🕒 {ist_t.strftime('%d %b, %I:%M %p')} IST")
                with c2:
                    h, rem = divmod(int(diff.total_seconds()), 3600)
                    m_left, _ = divmod(rem, 60)
                    st.warning(f"⏳ {h}h {m_left}m left")
                with c3:
                    st.code(m['id'])
                st.divider()

        # 2. IN-PROGRESS SECTION
        st.subheader("🔥 Live / In-Progress")
        if not live: st.write("No matches currently live.")
        for m in live:
            with st.expander(f"LIVE: {m['name']}", expanded=True):
                st.success(f"Status: {m['status']}")
                st.code(f"Match ID: {m['id']}")

        # 3. COMPLETED SECTION
        st.subheader("🏁 Completed Results")
        with st.expander("Show Recent Results"):
            for m in reversed(completed[-10:]):
                st.write(f"**{m['name']}**")
                st.info(m['status'])
                st.divider()
    else:
        st.error("API Limit reached or Key Invalid. Please check your CricAPI dashboard.")
