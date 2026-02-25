import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser

# --- CONFIG & SECRETS ---
API_KEY = st.secrets["CRICKET_API_KEY"]
SHEET_URL = st.secrets["GSHEET_URL"]

st.set_page_config(page_title="Family Fantasy Pro", page_icon="🏏", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SIDEBAR RULES ---
with st.sidebar:
    st.title("📜 Squad Rules")
    st.info("""
    - **Total Players:** 11
    - **Wicketkeepers:** Exactly 2
    - **Batsmen:** Max 6
    - **All-rounders:** Min 1
    - **Bowlers:** Min 1
    ---
    **Points:** Run=1, Wicket=25
    **Multipliers:** C=2x, VC=1.5x
    """)

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_live_matches():
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    try:
        res = requests.get(url).json()
        return res.get('data', [])
    except: return []

@st.cache_data(ttl=60)
def get_squad_details(match_id):
    url = f"https://api.cricapi.com/v1/match_squad?apikey={API_KEY}&id={match_id}"
    try:
        res = requests.get(url).json()
        all_players = []
        if res.get('status') == 'success':
            for team in res['data']:
                for p in team['players']:
                    all_players.append({
                        "name": p['name'],
                        "role": p.get('role', 'batsman').lower(),
                        "playing": p.get('status') == 'playing'
                    })
        return all_players
    except: return []

# --- 1. DEFINE TABS FIRST (Fixes NameError) ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 Live Scores", "📝 Create Team", "🏆 Leaderboard", "📜 History"])

# --- TAB 1: SERIES FINDER, TIMER & UPCOMING ---
with tab1:
    st.header("🔍 Series & Match Center")
    search_query = st.text_input("Search Series (e.g., 'IPL', 'India', 'T20'):", "").lower()
    
    matches = get_live_matches()
    
    if matches:
        filtered = [m for m in matches if search_query in m.get('name', '').lower()] if search_query else matches[:10]
        
        if filtered:
            live_now = [m for m in filtered if m['matchStarted']]
            upcoming = [m for m in filtered if not m['matchStarted']]

            if live_now:
                st.subheader("🏏 Matches in Progress")
                for m in live_now:
                    with st.expander(f"LIVE: {m['name']}", expanded=True):
                        st.write(f"📢 **Status:** {m['status']}")
                        st.code(f"Match ID: {m['id']}")

            if upcoming:
                st.divider()
                st.subheader("⏰ Upcoming Fixtures (Get Ready!)")
                for m in upcoming:
                    with st.container():
                        c1, c2, c3 = st.columns([2, 1, 1])
                        
                        # Time Calculations (IST is GMT + 5:30)
                        match_time_gmt = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
                        match_time_ist = match_time_gmt + timedelta(hours=5, minutes=30)
                        now = datetime.now(timezone.utc)
                        diff = match_time_gmt - now
                        
                        with c1:
                            st.write(f"**{m['name']}**")
                            st.caption(f"Starts: {match_time_ist.strftime('%d %b, %I:%M %p')} IST")
                        
                        with c2:
                            total_sec = diff.total_seconds()
                            if total_sec > 0:
                                hours, remainder = divmod(int(total_sec), 3600)
                                minutes, _ = divmod(remainder, 60)
                                # Red warning if under 30 minutes
                                if total_sec < 1800:
                                    st.error(f"🚨 LOCKING IN: {minutes}m left!")
                                else:
                                    st.warning(f"⏳ {hours}h {minutes}m left")
                            else:
                                st.success("🚀 Toss In Progress!")
                        
                        with c3:
                            st.code(m['id'])
                        st.divider()
        else:
            st.warning("No matches found for this series.")
