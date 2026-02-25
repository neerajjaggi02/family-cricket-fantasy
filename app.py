import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser

# --- CONFIG & SECRETS ---
# Using your new verified API Key and Host
RAPID_API_KEY = "adcb96e431mshd1c8f0f5f76b8b2p1052a5jsn8d4db86ab77d"
RAPID_API_HOST = "cricket-live-line1.p.rapidapi.com"
SHEET_URL = st.secrets["GSHEET_URL"]

headers = {
    'x-rapidapi-key': RAPID_API_KEY,
    'x-rapidapi-host': RAPID_API_HOST
}

st.set_page_config(page_title="Mumbai Fantasy Pro", page_icon="🏏", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SIDEBAR: FIXED RULES ---
with st.sidebar:
    st.header("🏆 League Rules")
    st.markdown("""
    **Squad Mix:**
    - 🧤 **2** Wicketkeepers
    - 🏏 **Max 6** Batsmen
    - ⚡ **Min 1** All-rounder
    - 🎾 **Min 1** Bowler
    ---
    **Points:** Run=1 | Wicket=25
    **Timezone:** Mumbai (IST)
    """)
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# --- API FUNCTIONS (LIVE LINE ADAPTER) ---
@st.cache_data(ttl=300)
def get_live_line_matches():
    # Attempting to fetch the match list from the new host
    # Note: Using /matchList as it is a common endpoint for this host
    url = f"https://{RAPID_API_HOST}/matchList/upcoming"
    try:
        res = requests.get(url, headers=headers).json()
        match_data = []
        # Live Line 1 often returns a 'data' object with a list
        matches = res.get('data', [])
        for m in matches:
            match_data.append({
                'id': m.get('match_id'),
                'name': f"{m.get('team_a')} vs {m.get('team_b')}",
                'series': m.get('series_name'),
                'status': m.get('match_status'),
                'timestamp': m.get('match_date_time'), # Usually ISO or Epoch
                'is_live': m.get('is_live', 0)
            })
        return match_data
    except:
        return []

# --- MAIN TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.header("🏏 Match Center (Live Line)")
    search_q = st.text_input("Search Team (e.g., 'India'):", "India").strip().lower()
    
    matches = get_live_line_matches()
    
    if matches:
        filtered = [m for m in matches if search_q in str(m['name']).lower() or search_q in str(m['series']).lower()]
        
        # Sectioning: Live vs Upcoming
        live_now = [m for m in filtered if m['is_live'] == 1]
        upcoming = [m for m in filtered if m['is_live'] == 0]

        # ⏳ SECTION 1: UPCOMING (Focus for Feb 26)
        st.subheader("📅 Upcoming Fixtures")
        if not upcoming: st.info("No upcoming matches found.")
        for m in upcoming:
            # Handle IST Conversion
            try:
                dt = dateutil.parser.isoparse(m['timestamp'])
                ist_t = dt.replace(tzinfo=timezone.utc) + timedelta(hours=5, minutes=30)
                diff = ist_t - (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30))
            except:
                ist_t = datetime.now()
                diff = timedelta(0)

            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.write(f"**{m['name']}**")
                    st.caption(f"🏆 {m['series']}")
                    st.caption(f"🕒 {ist_t.strftime('%d %b, %I:%M %p')} IST")
                with c2:
                    if diff.total_seconds() > 0:
                        h, rem = divmod(int(diff.total_seconds()), 3600)
                        ml, _ = divmod(rem, 60)
                        st.warning(f"⏳ {h}h {ml}m left")
                    else: st.info("🚀 Toss Soon")
                with c3:
                    st.write("Match ID:")
                    st.code(m['id'])
                st.divider()

        # 🏁 SECTION 2: IN-PROGRESS / RECENT
        st.subheader("🏁 Live & Recent")
        for m in live_now:
            with st.expander(f"LIVE: {m['name']} - {m['status']}"):
                st.code(f"Match ID: {m['id']}")
    else:
        st.error("📡 No matches found. Check if 'Cricket Live Line 1' is active in your RapidAPI dashboard.")
