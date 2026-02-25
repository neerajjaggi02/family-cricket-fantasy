import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd

# --- CONFIG & SECRETS ---
API_KEY = st.secrets["CRICKET_API_KEY"]
SHEET_URL = st.secrets["GSHEET_URL"]

st.set_page_config(page_title="Family Fantasy Pro", page_icon="🏏", layout="wide")

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_live_data():
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    return requests.get(url).json().get('data', [])

@st.cache_data(ttl=3600)
def get_squad(match_id):
    url = f"https://api.cricapi.com/v1/match_squad?apikey={API_KEY}&id={match_id}"
    res = requests.get(url).json()
    players = []
    if res.get('status') == 'success':
        for team in res['data']:
            players.extend([p['name'] for p in team['players']])
    return players

# --- UI TABS ---
tab1, tab2, tab3 = st.tabs(["📺 Live Scores", "📝 Create Team", "🏆 Leaderboard"])

# --- TAB 1: LIVE SCORES ---
with tab1:
    st.header("Live Match Tracking")
    matches = get_live_data()
    if matches:
        for m in matches[:2]: # Show first 2 matches
            with st.expander(f"{m['name']} - {m['status']}", expanded=True):
                st.write(f"**Match ID (Copy this for Team Creation):** `{m['id']}`")
                if m.get('score'):
                    st.metric("Current Score", f"{m['score'][0]['r']}/{m['score'][0]['w']} ({m['score'][0]['o']} ov)")

# --- TAB 2: CREATE TEAM ---
with tab2:
    st.header("Build Your XI")
    m_id = st.text_input("Paste Match ID from Live Scores tab:")
    
    if m_id:
        player_pool = get_squad(m_id)
        if player_pool:
            user = st.text_input("Enter Your Name:")
            selected = st.multiselect("Pick 11 Players:", player_pool, max_selections=11)
            
            if len(selected) == 11:
                cap = st.selectbox("Captain (2x):", selected)
                vc = st.selectbox("Vice-Captain (1.5x):", [p for p in selected if p != cap])
                
                if st.button("Submit Team to League"):
                    new_data = pd.DataFrame([{"User": user, "Players": ",".join(selected), "Captain": cap, "ViceCaptain": vc}])
                    # Logic to append to Google Sheets
                    existing_data = conn.read(spreadsheet=SHEET_URL)
                    updated_df = pd.concat([existing_data, new_data], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, data=updated_df)
                    st.success("Team Saved! Check the Leaderboard.")
                    st.balloons()

# --- TAB 3: LEADERBOARD ---
with tab3:
    st.header("Family Standings")
    try:
        league_table = conn.read(spreadsheet=SHEET_URL)
        
        # Simple Logic: Assign random points for demonstration since Free API 
        # doesn't give individual player stats in the 'currentMatches' endpoint.
        # In a real match, you'd compare 'Players' list against 'Scorecard' API.
        
        if not league_table.empty:
            # We add a "Dummy" point system based on match status for now
            league_table['Points'] = [750, 820, 690, 910][:len(league_table)] # Mock points
            st.table(league_table.sort_values("Points", ascending=False))
            
            top_user = league_table.iloc[0]['User']
            st.info(f"🌟 **{top_user}** is currently the Highest Scorer of the Day!")
    except:
        st.write("No teams submitted yet. Be the first!")

st.sidebar.markdown("---")
st.sidebar.write("Developed for Family Use Only 🏏")
