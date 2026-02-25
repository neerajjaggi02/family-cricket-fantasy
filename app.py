import streamlit as st
from streamlit_gsheets import GSheetsConnection
import requests
import pandas as pd

# --- CONFIG & SECRETS ---
API_KEY = st.secrets["CRICKET_API_KEY"]
SHEET_URL = st.secrets["GSHEET_URL"]

st.set_page_config(page_title="Family Fantasy Pro", page_icon="🏏", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SIDEBAR RULES ---
with st.sidebar:
    st.title("📜 Scoring Rules")
    st.markdown("""
    - **Run:** 1 pt
    - **Wicket:** 25 pts
    - **Captain (C):** 2x Points
    - **Vice-Captain (VC):** 1.5x Points
    ---
    *Refresh the app during match hours for live updates!*
    """)

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_live_matches():
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    try:
        return requests.get(url).json().get('data', [])
    except: return []

@st.cache_data(ttl=60)
def get_scorecard(match_id):
    if not match_id or pd.isna(match_id): return {}
    url = f"https://api.cricapi.com/v1/match_scorecard?apikey={API_KEY}&id={match_id}"
    try:
        res = requests.get(url).json()
        player_stats = {}
        if res.get('status') == 'success' and res.get('data'):
            scorecard = res['data'].get('scorecard', [])
            for inning in scorecard:
                for batter in inning.get('batting', []):
                    name = batter.get('content')
                    player_stats[name] = player_stats.get(name, 0) + int(batter.get('r', 0))
                for bowler in inning.get('bowling', []):
                    name = bowler.get('content')
                    player_stats[name] = player_stats.get(name, 0) + (int(bowler.get('w', 0)) * 25)
        return player_stats
    except: return {}

@st.cache_data(ttl=3600)
def get_squad(match_id):
    url = f"https://api.cricapi.com/v1/match_squad?apikey={API_KEY}&id={match_id}"
    try:
        res = requests.get(url).json()
        players = []
        if res.get('status') == 'success':
            for team in res['data']:
                players.extend([p['name'] for p in team['players']])
        return players
    except: return []

# --- UI TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 Live Scores", "📝 Create Team", "🏆 Leaderboard", "📜 History"])

# --- TAB 1: SERIES & MATCH FINDER ---
with tab1:
    st.header("🔍 Series & Match Finder")
    search_query = st.text_input("Search Series (e.g., 'IPL', 'India', 'T20'):", "").lower()
    matches = get_live_matches()
    
    if matches:
        filtered = [m for m in matches if search_query in m.get('name', '').lower()] if search_query else matches[:10]
        if filtered:
            for m in filtered:
                with st.container():
                    col_info, col_id = st.columns([3, 1])
                    with col_info:
                        st.subheader(m['name'])
                        st.write(f"📅 **Status:** {m['status']}")
                        if m.get('score'):
                            s = m['score'][0]
                            st.info(f"Score: {s['r']}/{s['w']} ({s['o']} ov)")
                    with col_id:
                        st.write("📋 **Match ID**")
                        st.code(m['id'])
                    st.divider()
        else: st.warning("No matches found.")
    else: st.info("No live matches.")

# --- TAB 2: CREATE TEAM ---
with tab2:
    st.header("📝 Join a Contest")
    m_id = st.text_input("Paste Match ID here:")
    if m_id:
        pool = get_squad(m_id)
        if pool:
            with st.form("team_form"):
                user = st.text_input("Your Name:")
                selected = st.multiselect("Pick 11 Players:", pool, max_selections=11)
                cap = st.selectbox("Captain (2x):", selected if selected else ["Pick players first"])
                vc = st.selectbox("Vice-Captain (1.5x):", [p for p in selected if p != cap] if selected else ["Pick players first"])
                if st.form_submit_button("Submit Team") and len(selected) == 11:
                    new_data = pd.DataFrame([{"User": user, "Players": ",".join(selected), "Captain": cap, "ViceCaptain": vc, "MatchID": m_id}])
                    existing = conn.read(spreadsheet=SHEET_URL)
                    conn.update(spreadsheet=SHEET_URL, data=pd.concat([existing, new_data], ignore_index=True))
                    st.success("Team saved!")

# --- TAB 3: LEADERBOARD ---
with tab3:
    st.header("🏆 Live Standings")
    active_id = st.text_input("Enter Match ID for Live Points:")
    if active_id:
        pts_map = get_scorecard(active_id)
        df = conn.read(spreadsheet=SHEET_URL)
        m_teams = df[df['MatchID'] == active_id]
        if not m_teams.empty:
            results = []
            for _, row in m_teams.iterrows():
                score = 0
                for p in str(row['Players']).split(","):
                    p_pts = pts_map.get(p, 0)
                    m = 2 if p == row['Captain'] else (1.5 if p == row['ViceCaptain'] else 1)
                    score += p_pts * m
                results.append({"User": row['User'], "Score": score})
            st.table(pd.DataFrame(results).sort_values("Score", ascending=False))
        else: st.info("No teams for this Match ID.")

# --- TAB 4: HISTORY & SEASON ---
with tab4:
    st.header("📜 Hall of Fame")
    try:
        all_h = conn.read(spreadsheet=SHEET_URL, ttl=0)
        history_list = []
        if not all_h.empty:
            for mid in all_h['MatchID'].unique():
                pts = get_scorecard(mid)
                m_t = all_h[all_h['MatchID'] == mid]
                scores = []
                for _, r in m_t.iterrows():
                    s = sum(pts.get(p,0) * (2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))
                    scores.append({"User": r['User'], "Score": s})
                if scores:
                    win = max(scores, key=lambda x: x['Score'])
                    history_list.append({"Match ID": mid, "Winner": win['User'], "Winning Score": win['Score']})
            st.dataframe(pd.DataFrame(history_list), use_container_width=True, hide_index=True)
            
            st.divider()
            st.subheader("🏅 Overall Season Standings")
            standings = pd.DataFrame(history_list)['Winner'].value_counts().reset_index()
            standings.columns = ['Member', 'Wins']
            st.dataframe(standings.style.highlight_max(subset=['Wins'], color='gold'), use_container_width=True, hide_index=True)
    except: st.error("Please ensure Google Sheet is shared and API is enabled.")
