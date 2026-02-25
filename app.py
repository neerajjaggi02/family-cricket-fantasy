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
@st.cache_data(ttl=300)
def get_live_matches():
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    return requests.get(url).json().get('data', [])

@st.cache_data(ttl=60)
def get_scorecard(match_id):
    # Safety check: if match_id is empty or NaN, return empty stats
    if not match_id or pd.isna(match_id):
        return {}
        
    url = f"https://api.cricapi.com/v1/match_scorecard?apikey={API_KEY}&id={match_id}"
    try:
        response = requests.get(url)
        # Check if the API returned a 200 OK status
        if response.status_code != 200:
            return {}
            
        res = response.json()
        player_stats = {}
        
        if res.get('status') == 'success' and res.get('data'):
            data = res.get('data', {})
            # Process scorecard safely
            scorecard = data.get('scorecard', [])
            if not scorecard:
                return {}
                
            for inning in scorecard:
                # Process Batting
                for batter in inning.get('batting', []):
                    name = batter.get('content', 'Unknown')
                    runs = batter.get('r', 0)
                    # Convert to int safely
                    player_stats[name] = player_stats.get(name, 0) + int(runs if str(runs).isdigit() else 0)
                
                # Process Bowling
                for bowler in inning.get('bowling', []):
                    name = bowler.get('content', 'Unknown')
                    wickets = bowler.get('w', 0)
                    player_stats[name] = player_stats.get(name, 0) + (int(wickets if str(wickets).isdigit() else 0) * 25)
        return player_stats
    except Exception:
        return {} # Return empty dict if API fails or JSON is invalid

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
tab1, tab2, tab3, tab4 = st.tabs(["📺 Live Scores", "📝 Create Team", "🏆 Leaderboard", "📜 History"])

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
                selected = st.multiselect("Pick 11 Players:", player_pool, max_selections=11)
                cap = st.selectbox("Captain (2x):", selected if selected else ["Pick 11 players"])
                vc = st.selectbox("Vice-Captain (1.5x):", [p for p in selected if p != cap] if selected else ["Pick 11 players"])
                submit = st.form_submit_button("Save Team")
                
                if submit and len(selected) == 11:
                    new_team = pd.DataFrame([{"User": user, "Players": ",".join(selected), "Captain": cap, "ViceCaptain": vc, "MatchID": m_id}])
                    existing = conn.read(spreadsheet=SHEET_URL)
                    updated = pd.concat([existing, new_team], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, data=updated)
                    st.success(f"Team saved for match {m_id}!")

# --- TAB 3: LEADERBOARD ---
with tab3:
    st.header("Live Rankings")
    active_id = st.text_input("Enter Match ID to see Live Points:")
    if active_id:
        pts_map = get_scorecard(active_id)
        all_teams = conn.read(spreadsheet=SHEET_URL)
        match_teams = all_teams[all_teams['MatchID'] == active_id]
        
        if not match_teams.empty:
            leaderboard = []
            for _, row in match_teams.iterrows():
                u_total = 0
                for p in row['Players'].split(","):
                    p_pts = pts_map.get(p, 0)
                    mult = 2 if p == row['Captain'] else (1.5 if p == row['ViceCaptain'] else 1)
                    u_total += p_pts * mult
                leaderboard.append({"User": row['User'], "Score": u_total})
            st.table(pd.DataFrame(leaderboard).sort_values("Score", ascending=False))
        else:
            st.info("No teams submitted for this Match ID yet.")

# --- TAB 4: HISTORY (HALL OF FAME) ---
with tab4:
    st.header("📜 Past Winners")
    
    # --- SAFER READ LOGIC START ---
    try:
        # We use ttl=0 to make sure it doesn't show old "Permission Denied" errors from cache
        all_history = conn.read(spreadsheet=SHEET_URL, ttl=0)
    except Exception as e:
        st.error("⚠️ Connection Error: Cannot reach Google Sheets.")
        st.info("Check: 1. Is Google Drive API enabled? 2. Is the sheet shared with the service account email as Editor?")
        # Create an empty table so the code below doesn't crash
        all_history = pd.DataFrame(columns=["User", "Players", "Captain", "ViceCaptain", "MatchID"])
    # --- SAFER READ LOGIC END ---

    history_list = [] # Initialize this so the standings logic below doesn't error out

    if not all_history.empty:
        unique_matches = all_history['MatchID'].unique()
        
        for mid in unique_matches:
            # We calculate final scores for each match in history
            hist_pts_map = get_scorecard(mid)
            hist_match_teams = all_history[all_history['MatchID'] == mid]
            
            temp_leaderboard = []
            for _, row in hist_match_teams.iterrows():
                u_total = 0
                for p in str(row['Players']).split(","):
                    p_pts = hist_pts_map.get(p, 0)
                    mult = 2 if p == row['Captain'] else (1.5 if p == row['ViceCaptain'] else 1)
                    u_total += p_pts * mult
                temp_leaderboard.append({"User": row['User'], "Score": u_total})
            
            # Find the winner for this specific MatchID
            if temp_leaderboard:
                winner_row = max(temp_leaderboard, key=lambda x: x['Score'])
                history_list.append({"Match ID": mid, "Winner": winner_row['User'], "Winning Score": winner_row['Score']})
        
        if history_list:
            st.dataframe(pd.DataFrame(history_list), use_container_width=True, hide_index=True)
        else:
            st.write("No winners declared yet.")
    else:
        st.write("No history available yet. Submit a team in Tab 2 to start!")

    # --- SEASON STANDINGS (MOST WINS) ---
    st.divider()
    st.subheader("🏅 Season Standings (Most Wins)")

    if history_list:
        history_df = pd.DataFrame(history_list)
        standings = history_df['Winner'].value_counts().reset_index()
        standings.columns = ['Family Member', 'Total Match Wins']
        st.dataframe(standings.style.highlight_max(axis=0, color='gold'), use_container_width=True, hide_index=True)
    else:
        st.write("Play a match to see the season rankings!")
