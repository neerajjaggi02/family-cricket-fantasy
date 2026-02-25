import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser

# --- CONFIG & SECRETS ---
# Use the headers you got from RapidAPI
RAPID_API_KEY = "97efb164-e552-4332-93a8-60aaaefe0f1d" # Your provided Key
RAPID_API_HOST = "cricbuzz-cricket.p.rapidapi.com"
SHEET_URL = st.secrets["GSHEET_URL"]

headers = {
    'x-rapidapi-key': RAPID_API_KEY,
    'x-rapidapi-host': RAPID_API_HOST
}

st.set_page_config(page_title="Family Fantasy Pro", page_icon="🏏", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS (CRICBUZZ VERSION) ---
@st.cache_data(ttl=300)
def get_all_matches():
    """Fetches list of all international and league matches."""
    url = f"https://{RAPID_API_HOST}/matches/list"
    try:
        res = requests.get(url, headers=headers).json()
        match_list = []
        # Cricbuzz groups by 'type' (International, League, etc)
        for category in res.get('typeMatches', []):
            for series in category.get('seriesMatches', []):
                for match in series.get('seriesAdWrapper', {}).get('matches', []):
                    # Standardizing format for our app
                    match_info = match.get('matchInfo', {})
                    match_list.append({
                        'id': match_info.get('matchId'),
                        'name': f"{match_info.get('team1', {}).get('teamName')} vs {match_info.get('team2', {}).get('teamName')}",
                        'status': match_info.get('status'),
                        'dateTimeGMT': int(match_info.get('startDate')), # This is usually Epoch in Cricbuzz
                        'matchStarted': match_info.get('state') != 'Upcoming'
                    })
        return match_list
    except: return []

@st.cache_data(ttl=60)
def get_scorecard(match_id):
    """Fetches scorecard using your provided hscard endpoint."""
    url = f"https://{RAPID_API_HOST}/mcenter/v1/{match_id}/hscard"
    try:
        res = requests.get(url, headers=headers).json()
        player_stats = {}
        # Cricbuzz scorecard structure
        for inning in res.get('scoreCard', []):
            # Batting points
            for b in inning.get('batTeamDetails', {}).get('batsmenData', {}).values():
                name = b.get('batName')
                player_stats[name] = player_stats.get(name, 0) + int(b.get('runs', 0))
            # Bowling points
            for bo in inning.get('bowlTeamDetails', {}).get('bowlersData', {}).values():
                name = bo.get('bowlName')
                player_stats[name] = player_stats.get(name, 0) + (int(bo.get('wickets', 0)) * 25)
        return player_stats
    except: return {}

# --- SIDEBAR & TABS ---
with st.sidebar:
    st.header("🏆 League Rules")
    st.info("🧤 2 WK | 🏏 Max 6 Bat\n\n⚡ 1 AR | 🎾 1 Bowl")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.subheader("🏏 Live, Upcoming & Results")
    search_q = st.text_input("Filter matches (e.g., 'India'):", "").lower()
    
    all_m = get_all_matches()
    filtered = [m for m in all_m if search_q in m['name'].lower()] if search_q else all_m[:15]

    # Split into sections
    upcoming = [m for m in filtered if not m['matchStarted']]
    live_comp = [m for m in filtered if m['matchStarted']]

    st.markdown("### 📅 Upcoming Matches")
    for m in upcoming:
        # Cricbuzz time is in milliseconds
        ist_t = datetime.fromtimestamp(m['dateTimeGMT']/1000, tz=timezone.utc) + timedelta(hours=5, minutes=30)
        with st.container():
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"**{m['name']}**")
                st.caption(f"🕒 {ist_t.strftime('%d %b, %I:%M %p')} IST")
            with c2:
                st.warning("⏳ Upcoming")
            with c3:
                st.code(m['id'])
            st.divider()

    st.markdown("### 🏁 Live & Recent Results")
    for m in live_comp:
        with st.expander(f"{m['name']} - {m['status']}"):
            st.write(f"**Match ID:** `{m['id']}`")
