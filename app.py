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

# --- SIDEBAR (Always there) ---
with st.sidebar:
    st.header("🏆 League Rules")
    st.info("🧤 2 WK Required | 🏏 Max 6 Bat | ⚡ Min 1 AR | 🎾 Min 1 Bowl")
    st.divider()
    if st.button("🔄 FORCE REFRESH"):
        st.cache_data.clear()
        st.rerun()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- THE "AGGRESSIVE" API FETCH ---
@st.cache_data(ttl=300)
def get_all_matches_v2():
    # We hit multiple endpoints to ensure no match is missed
    endpoints = [
        f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0",
        f"https://api.cricapi.com/v1/matches?apikey={API_KEY}&offset=0"
    ]
    all_raw = []
    for url in endpoints:
        try:
            res = requests.get(url).json()
            if res.get("status") == "success":
                all_raw.extend(res.get("data", []))
        except: continue
    
    # Remove duplicates by Match ID
    unique_data = {m['id']: m for m in all_raw}.values()
    return sorted(list(unique_data), key=lambda x: x['dateTimeGMT'])

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.subheader("🔍 Universal Match Finder")
    # Default search to 'India' to help find the next big game immediately
    s_query = st.text_input("Search Team or Series (e.g. India, World Cup):", "India").strip().lower()
    
    data = get_all_matches_v2()
    
    if data:
        # SEARCH LOGIC: Check name, series, and teams array
        filtered = []
        for m in data:
            m_name = m.get('name', '').lower()
            m_series = m.get('series_id', '').lower() # Some APIs put series name here
            m_teams = [t.lower() for t in m.get('teams', [])]
            
            if s_query in m_name or s_query in m_series or any(s_query in t for t in m_teams):
                filtered.append(m)
        
        if filtered:
            # Split into Current and Future
            now = datetime.now(timezone.utc)
            
            # --- SECTION: UPCOMING ---
            st.markdown("### 📅 Upcoming Fixtures")
            upcoming_found = False
            for m in filtered:
                match_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
                if match_time > now and not m.get('matchStarted'):
                    upcoming_found = True
                    ist_t = match_time + timedelta(hours=5, minutes=30)
                    diff = match_time - now
                    with st.container():
                        c1, c2, c3 = st.columns([2, 1, 1])
                        with c1:
                            st.markdown(f"**{m['name']}**")
                            st.caption(f"🕒 {ist_t.strftime('%d %b, %I:%M %p')} IST")
                        with c2:
                            h, rem = divmod(int(diff.total_seconds()), 3600)
                            ml, _ = divmod(rem, 60)
                            st.warning(f"⏳ {h}h {ml}m left")
                        with c3:
                            st.code(m['id'])
                        st.divider()
            if not upcoming_found: st.write("No future matches found for this search.")

            # --- SECTION: LIVE/COMPLETED ---
            st.markdown("### 🏁 Live & Recent")
            for m in filtered:
                match_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
                if m.get('matchStarted') or now >= match_time:
                    with st.expander(f"{m['name']} ({m.get('status', 'Recent')})"):
                        st.write(f"Match ID: `{m['id']}`")
                        st.write(f"Venue: {m.get('venue')}")
        else:
            st.warning(f"No results for '{s_query}'. Try searching just 'ICC' or 'Cup'.")
    else:
        st.error("API Error: No data returned. Please check your internet or API key limits.")
