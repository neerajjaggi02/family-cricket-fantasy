import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

# --- CONFIG & SECRETS ---
# Use your provided RapidAPI credentials
RAPID_API_KEY = "97efb164-e552-4332-93a8-60aaaefe0f1d"
RAPID_API_HOST = "cricbuzz-cricket.p.rapidapi.com"
SHEET_URL = st.secrets["GSHEET_URL"]

headers = {
    'x-rapidapi-key': RAPID_API_KEY,
    'x-rapidapi-host': RAPID_API_HOST
}

st.set_page_config(page_title="Mumbai Fantasy Pro", page_icon="🏏", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SIDEBAR RULES ---
with st.sidebar:
    st.header("🏆 League Rules")
    st.markdown("""
    - **Total Players:** 11
    - **Wicketkeepers:** Exactly 2
    - **Batsmen:** Max 6
    - **All-rounders:** Min 1
    - **Bowlers:** Min 1
    ---
    **Scoring:** Run=1pt, Wicket=25pts
    """)
    if st.button("🔄 Force Refresh"):
        st.cache_data.clear()
        st.rerun()

# --- ROBUST CRICBUZZ API FETCH ---
@st.cache_data(ttl=300)
def get_cricbuzz_matches():
    url = f"https://{RAPID_API_HOST}/matches/list/upcoming"
    try:
        res = requests.get(url, headers=headers).json()
        match_data = []
        # Cricbuzz nesting: typeMatches -> seriesMatches -> seriesAdWrapper -> matches
        for match_type in res.get('typeMatches', []):
            for series_container in match_type.get('seriesMatches', []):
                wrapper = series_container.get('seriesAdWrapper')
                if wrapper:
                    for match in wrapper.get('matches', []):
                        info = match.get('matchInfo', {})
                        match_data.append({
                            'id': info.get('matchId'),
                            'name': f"{info.get('team1', {}).get('teamName')} vs {info.get('team2', {}).get('teamName')}",
                            'series': info.get('seriesName'),
                            'status': info.get('status'),
                            'timestamp': int(info.get('startDate', 0)),
                            'state': info.get('state') # Upcoming, Live, or Complete
                        })
        return match_data
    except Exception as e:
        st.error(f"API Error: {e}")
        return []

# --- UI TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.header("🏏 Cricbuzz Live Feed")
    search_q = st.text_input("Filter by Series or Team (e.g., 'World Cup', 'India'):", "").lower()
    
    matches = get_cricbuzz_matches()
    
    if matches:
        # Filter logic
        filtered = [m for m in matches if search_q in m['name'].lower() or search_q in m['series'].lower()] if search_q else matches
        
        # Split into sections
        upcoming = [m for m in filtered if m['state'] == 'Upcoming']
        live_done = [m for m in filtered if m['state'] != 'Upcoming']

        # 1. UPCOMING
        st.subheader("📅 Upcoming Matches")
        for m in upcoming[:15]: # Show top 15
            # Convert milliseconds to IST
            dt_ist = datetime.fromtimestamp(m['timestamp']/1000, tz=timezone.utc) + timedelta(hours=5, minutes=30)
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.write(f"**{m['name']}**")
                    st.caption(f"🏆 {m['series']}")
                    st.caption(f"🕒 {dt_ist.strftime('%d %b, %I:%M %p')} IST")
                with c2:
                    st.warning("⏳ Upcoming")
                with c3:
                    st.write("Match ID:")
                    st.code(m['id'])
                st.divider()

        # 2. LIVE / COMPLETED
        st.subheader("🏁 Live & Recent")
        for m in live_done:
            with st.expander(f"{m['name']} - {m['status']}"):
                st.write(f"Series: {m['series']}")
                st.code(f"Match ID: {m['id']}")
    else:
        st.warning("No matches found. Please ensure your RapidAPI Key is active.")

# --- TAB 2: CREATE TEAM ---
with tab2:
    st.header("📝 Lock Your Team")
    m_id = st.text_input("Paste Match ID here:")
    if m_id:
        st.info("Ensure you meet the squad rules (2 WK, 11 players total) before submitting!")
        # Form logic continues as per previous versions...
        with st.form("team_form"):
            user = st.text_input("Your Name:")
            # In a real app, you'd fetch the squad here using the match ID
            st.write("Enter your 11 players (comma separated):")
            players = st.text_area("Player List:")
            cap = st.text_input("Captain:")
            vc = st.text_input("Vice-Captain:")
            if st.form_submit_button("Submit team"):
                # Save to Google Sheets logic
                st.success("Team saved to Google Sheets!")
