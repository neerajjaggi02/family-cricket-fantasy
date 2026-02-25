import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd

# --- CONFIG & SECRETS ---
API_KEY = st.secrets["CRICKET_API_KEY"]
SHEET_URL = st.secrets["GSHEET_URL"]

st.set_page_config(page_title="Family Fantasy Pro", page_icon="🏏", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS ---
@st.cache_data(ttl=120)
def get_live_matches():
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    return requests.get(url).json().get('data', [])

@st.cache_data(ttl=60)
def get_scorecard(match_id):
    url = f"https://api.cricapi.com/v1/match_scorecard?apikey={API_KEY}&id={match_id}"
    res = requests.get(url).json()
    player_stats = {}
    if res.get('status') == 'success':
        data = res.get('data', {})
        # Process Batting
        for inning in data.get('scorecard', []):
            for batter in inning.get('batting', []):
                name = batter['content']
                r = int(batter.get('r', 0))
                player_stats[name] = player_stats.get(name, 0) + r
            # Process Bowling
            for bowler in inning.get('bowling', []):
                name = bowler['content']
                w = int(bowler.get('w', 0))
                player_stats[name] = player_stats.get(name, 0) + (w * 25) # 25 pts per wicket
    return player_stats

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
    st.header("Active Matches")
    matches = get_live_matches()
    if matches:
        for m in matches[:3]:
            with st.expander(f"{m['name']} ({m['status']})", expanded=True):
                st.code(f"Match ID: {m['id']}")
                if m.get('score'):
                    st.write(f"**Score:** {m['score'][0]['r']}/{m['score'][0]['w']} in {m['score'][0]['o']} overs")

# --- TAB 2: CREATE TEAM ---
with tab2:
    st.header("Submit Your Squad")
    m_id = st.text_input("Enter Match ID to join:")
    if m_id:
        player_pool = get_squad(m_id)
        if player_pool:
            with st.form("team_form"):
                user = st.text_input("Your Name:")
                selected = st.multiselect("Select 11 Players:", player_pool, max_selections=11)
                cap = st.selectbox("Captain (2x):", selected if selected else ["Select 11 players first"])
                vc = st.selectbox("Vice-Captain (1.5x):", [p for p in selected if p != cap] if selected else ["Select 11 players first"])
                submit = st.form_submit_button("Save Team")
                
                if submit and len(selected) == 11:
                    new_team = pd.DataFrame([{"User": user, "Players": ",".join(selected), "Captain": cap, "ViceCaptain": vc, "MatchID": m_id}])
                    existing = conn.read(spreadsheet=SHEET_URL)
                    updated = pd.concat([existing, new_team], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, data=updated)
                    st.success(f"Team saved for match {m_id}!")

# --- TAB 3: LEADERBOARD ---
with tab3:
    st.header("Fantasy Rankings")
    active_id = st.text_input("Enter Match ID to calculate points:")
    
    if active_id:
        # 1. Fetch live player points for this match
        pts_map = get_scorecard(active_id)
        
        # 2. Get saved teams
        all_teams = conn.read(spreadsheet=SHEET_URL)
        match_teams = all_teams[all_teams['MatchID'] == active_id]
        
        if not match_teams.empty:
            leaderboard = []
            for _, row in match_teams.iterrows():
                u_total = 0
                p_list = row['Players'].split(",")
                for p in p_list:
                    p_pts = pts_map.get(p, 0) # Get real points from scorecard
                    if p == row['Captain']: u_total += p_pts * 2
                    elif p == row['ViceCaptain']: u_total += p_pts * 1.5
                    else: u_total += p_pts
                leaderboard.append({"User": row['User'], "Score": u_total})
            
            final_df = pd.DataFrame(leaderboard).sort_values("Score", ascending=False)
            st.table(final_df)
            
            if not final_df.empty:
                winner = final_df.iloc[0]['User']
                st.balloons()
                st.success(f"🔥 Current Leader: **{winner}** with {final_df.iloc[0]['Score']} points!")
        else:
            st.warning("No teams found for this Match ID.")
