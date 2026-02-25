import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser

# --- CONFIG & SECRETS ---
API_KEY = st.secrets["CRICKET_API_KEY"]
SHEET_URL = st.secrets["GSHEET_URL"]

st.set_page_config(page_title="Mumbai City Fantasy", page_icon="🏏", layout="wide")

# --- SIDEBAR: ALWAYS VISIBLE RULES ---
with st.sidebar:
    st.header("🏆 League Rules")
    st.markdown("""
    ### **Squad Rules**
    * 🧤 **2** Wicketkeepers
    * 🏏 **Max 6** Batsmen
    * ⚡ **Min 1** All-rounder
    * 🎾 **Min 1** Bowler
    
    ### **Points Table**
    * 🏃 **1 Run:** 1 pt
    * विकेट **1 Wicket:** 25 pts
    * 🎖️ **Captain:** 2x
    * 🎖️ **Vice-Cap:** 1.5x
    
    ---
    *Lineups appear ~30m before Toss.*
    """)
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_all_matches():
    # Fetch from both to ensure we get current results + future schedule
    curr = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    mast = f"https://api.cricapi.com/v1/matches?apikey={API_KEY}&offset=0"
    try:
        c_res = requests.get(curr).json().get('data', [])
        m_res = requests.get(mast).json().get('data', [])
        combined = {m['id']: m for m in (c_res + m_res)}.values()
        return sorted(list(combined), key=lambda x: x['dateTimeGMT'])
    except: return []

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER (TWO SECTIONS) ---
with tab1:
    search_q = st.text_input("🔍 Search Series (e.g., 'World Cup', 'India'):", "World Cup").lower()
    all_m = get_all_matches()
    
    if all_m:
        filtered = [m for m in all_m if search_q in m.get('name', '').lower()]
        
        # Split into two lists
        live_completed = []
        upcoming = []
        
        for m in filtered:
            gmt_t = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            
            # If match started or finished
            if m.get('matchStarted') or now > gmt_t:
                live_completed.append(m)
            else:
                upcoming.append(m)

        # SECTION 1: UPCOMING
        st.header("⏳ Upcoming Matches")
        if not upcoming:
            st.write("No upcoming matches found for this search.")
        else:
            for m in upcoming:
                gmt_t = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
                ist_t = gmt_t + timedelta(hours=5, minutes=30)
                diff = gmt_t - now
                with st.container():
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.subheader(m['name'])
                        st.write(f"📅 **IST:** {ist_t.strftime('%d %b, %I:%M %p')}")
                    with c2:
                        h, rem = divmod(int(diff.total_seconds()), 3600)
                        m_l, _ = divmod(rem, 60)
                        st.warning(f"⏳ {h}h {m_l}m until start")
                    with c3:
                        st.write("ID for Tab 2:")
                        st.code(m['id'])
                    st.divider()

        # SECTION 2: IN-PROGRESS / COMPLETED
        st.header("🏏 Live & Recent Results")
        if not live_completed:
            st.write("No active or recent matches.")
        else:
            for m in reversed(live_completed[:10]): # Show last 10
                with st.expander(f"{m['name']} - {m['status']}"):
                    st.write(f"**Status:** {m['status']}")
                    st.code(f"Match ID: {m['id']}")
    else:
        st.error("Could not fetch matches.")
