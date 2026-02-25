import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd
from datetime import datetime, timezone
import dateutil.parser

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_live_matches():
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    try:
        res = requests.get(url).json()
        return res.get('data', [])
    except: return []

# --- TAB 1: SERIES FINDER, TIMER & UPCOMING ---
with tab1:
    st.header("🔍 Series & Match Center")
    search_query = st.text_input("Search Series (e.g., 'IPL', 'India', 'T20'):", "").lower()
    
    matches = get_live_matches()
    
    if matches:
        # Filter matches based on series search
        filtered = [m for m in matches if search_query in m.get('name', '').lower()] if search_query else matches[:10]
        
        if filtered:
            # Separate into LIVE and UPCOMING
            live_now = [m for m in filtered if m['matchStarted']]
            upcoming = [m for m in filtered if not m['matchStarted']]

            if live_now:
                st.subheader("🏏 Matches in Progress")
                for m in live_now:
                    with st.expander(f"LIVE: {m['name']}", expanded=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"📢 **Status:** {m['status']}")
                            if m.get('score'):
                                s = m['score'][0]
                                st.info(f"Current Score: {s['r']}/{s['w']} ({s['o']} ov)")
                        with col2:
                            st.write("📋 **Match ID**")
                            st.code(m['id'])

            if upcoming:
                st.divider()
                st.subheader("⏰ Upcoming Fixtures (Get Ready!)")
                for m in upcoming:
                    with st.container():
                        c1, c2, c3 = st.columns([2, 1, 1])
                        
                        # Calculate Countdown
                        match_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        diff = match_time - now
                        
                        with c1:
                            st.write(f"**{m['name']}**")
                            st.caption(f"Starts: {match_time.strftime('%d %b, %I:%M %p')} GMT")
                        
                        with c2:
                            if diff.total_seconds() > 0:
                                hours, remainder = divmod(int(diff.total_seconds()), 3600)
                                minutes, _ = divmod(remainder, 60)
                                st.warning(f"⏳ {hours}h {minutes}m left")
                            else:
                                st.success("🚀 Starting now!")
                        
                        with c3:
                            st.write("📋 **Match ID**")
                            st.code(m['id'])
                        st.divider()
        else:
            st.warning("No matches found for this series.")
    else:
        st.info("No matches found. Check your API key or internet connection.")
