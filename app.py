import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser

# --- CONFIG & SECRETS ---
# Using your verified RapidAPI Key
RAPID_API_KEY = "adcb96e431mshd1c8f0f5f76b8b2p1052a5jsn8d4db86ab77d"
RAPID_API_HOST = "cricbuzz-cricket.p.rapidapi.com"
SHEET_URL = st.secrets["GSHEET_URL"]

headers = {
    'x-rapidapi-key': RAPID_API_KEY,
    'x-rapidapi-host': RAPID_API_HOST
}

st.set_page_config(page_title="Mumbai Fantasy Pro", page_icon="🏏", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SIDEBAR: ALWAYS VISIBLE RULES ---
with st.sidebar:
    st.header("🏆 League Rules")
    st.markdown("""
    - 🧤 **2** Wicketkeepers
    - 🏏 **Max 6** Batsmen
    - ⚡ **Min 1** All-rounder
    - 🎾 **Min 1** Bowler
    ---
    **Points:** Run=1 | Wicket=25
    **Multipliers:** C=2x | VC=1.5x
    """)
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# --- API FUNCTIONS (CRICBUZZ MASTER LIST) ---
@st.cache_data(ttl=300)
def get_cricbuzz_matches():
    # This endpoint gets the master list of all current/future games
    url = f"https://{RAPID_API_HOST}/matches/list"
    try:
        res = requests.get(url, headers=headers).json()
        match_data = []
        # Cricbuzz nesting: typeMatches -> seriesMatches -> seriesAdWrapper -> matches
        for m_type in res.get('typeMatches', []):
            for s_match in m_type.get('seriesMatches', []):
                wrapper = s_match.get('seriesAdWrapper')
                if wrapper:
                    for m in wrapper.get('matches', []):
                        info = m.get('matchInfo', {})
                        match_data.append({
                            'id': info.get('matchId'),
                            'name': f"{info.get('team1', {}).get('teamName')} vs {info.get('team2', {}).get('teamName')}",
                            'series': info.get('seriesName'),
                            'status': info.get('status'),
                            'timestamp': int(info.get('startDate', 0)),
                            'state': info.get('state') # Upcoming, Live, or Complete
                        })
        return match_data
    except: return []

# --- MAIN TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.header("🏏 Cricbuzz World Cup Feed")
    search_q = st.text_input("Search Team or Series:", "India").strip().lower()
    
    matches = get_cricbuzz_matches()
    
    if matches:
        # Smart Filter
        filtered = [m for m in matches if search_q in m['name'].lower() or search_q in m['series'].lower()]
        
        # Categorize
        upcoming = [m for m in filtered if m['state'] == 'Upcoming']
        live_done = [m for m in filtered if m['state'] != 'Upcoming']

        # ⏳ SECTION 1: UPCOMING
        st.subheader("📅 Upcoming Fixtures")
        if not upcoming: st.info("No upcoming matches found for this search.")
        for m in upcoming:
            # Convert millisecond timestamp to IST
            dt_ist = datetime.fromtimestamp(m['timestamp']/1000, tz=timezone.utc) + timedelta(hours=5, minutes=30)
            diff = dt_ist - (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30))
            
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"**{m['name']}**")
                    st.caption(f"🏆 {m['series']}")
                    st.caption(f"🕒 {dt_ist.strftime('%d %b, %I:%M %p')} IST")
                with c2:
                    if diff.total_seconds() > 0:
                        h, rem = divmod(int(diff.total_seconds()), 3600)
                        ml, _ = divmod(rem, 60)
                        st.warning(f"⏳ {h}h {ml}m left")
                    else: st.info("🚀 Starting Soon")
                with c3:
                    st.write("Match ID:")
                    st.code(m['id'])
                st.divider()

        # 🏁 SECTION 2: LIVE & RECENT
        st.subheader("🏁 Live & Recent Results")
        for m in live_done:
            with st.expander(f"{m['name']} - {m['status']}"):
                st.write(f"**Series:** {m['series']}")
                st.code(f"**Match ID:** {m['id']}")
    else:
        st.error("No matches found. Please check your RapidAPI subscription for Cricbuzz.")
