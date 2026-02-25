import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser

# --- CONFIG & SECRETS ---
RAPID_API_KEY = "adcb96e431mshd1c8f0f5f76b8b2p1052a5jsn8d4db86ab77d"
RAPID_API_HOST = "free-cricbuzz-cricket-api.p.rapidapi.com"
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

# --- API FUNCTIONS (FREE CRICBUZZ ADAPTER) ---
@st.cache_data(ttl=300)
def get_matches():
    # Fetching the main match list from the Free API
    url = f"https://{RAPID_API_HOST}/matches" # Adjusting endpoint based on common Free API structures
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        
        # Mapping the Free API's response to our app's needs
        match_data = []
        # Note: The 'free' API often returns a list directly or under 'matches'
        matches = res.get('matches', res) if isinstance(res, dict) else res
        
        for m in matches:
            match_data.append({
                'id': m.get('match_id', m.get('id')),
                'name': m.get('match_name', f"{m.get('team1')} vs {m.get('team2')}"),
                'series': m.get('series_name', 'International'),
                'status': m.get('status', 'Upcoming'),
                'timestamp': m.get('start_date', 0),
                'state': m.get('state', 'Upcoming')
            })
        return match_data
    except Exception as e:
        return []

# --- MAIN TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.header("🏏 Match Center")
    search_q = st.text_input("Search Team or Series (e.g., 'India'):", "India").strip().lower()
    
    matches = get_matches()
    
    if matches:
        filtered = [m for m in matches if search_q in str(m['name']).lower()]
        
        # Filter for Upcoming vs Completed
        upcoming = [m for m in filtered if m['state'].lower() == 'upcoming']
        live_done = [m for m in filtered if m['state'].lower() != 'upcoming']

        st.subheader("📅 Upcoming Fixtures")
        if not upcoming: st.info("No upcoming matches found.")
        for m in upcoming:
            # Handle IST Conversion
            # Assuming Free API uses ISO string or Epoch
            try:
                dt = dateutil.parser.isoparse(m['timestamp']) if isinstance(m['timestamp'], str) else datetime.fromtimestamp(m['timestamp'])
                ist_t = dt.replace(tzinfo=timezone.utc) + timedelta(hours=5, minutes=30)
            except:
                ist_t = datetime.now() # Fallback

            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.write(f"**{m['name']}**")
                    st.caption(f"🏆 {m['series']}")
                    st.caption(f"🕒 {ist_t.strftime('%d %b, %I:%M %p')} IST")
                with c2:
                    st.warning("⏳ Entry Open")
                with c3:
                    st.write("Match ID:")
                    st.code(m['id'])
                st.divider()

        st.subheader("🏁 Live & Recent")
        for m in live_done:
            with st.expander(f"{m['name']} - {m['status']}"):
                st.code(f"Match ID: {m['id']}")
    else:
        st.warning("No matches found. Check if your new RapidAPI Host is active.")

# --- TAB 2: CREATE TEAM (LOGIC) ---
with tab2:
    st.subheader("📝 Submit Your Team")
    # ... Rest of your existing Team Creation logic ...
    st.info("Paste the Match ID from Tab 1 to start building your squad.")
