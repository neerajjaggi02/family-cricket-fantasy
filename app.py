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

# Custom GUI Styling
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 10px 10px 0 0; gap: 1px; padding-top: 10px; }
    .stTabs [aria-selected="true"] { background-color: #007bff; color: white !important; }
    div[data-testid="stExpander"] { border-radius: 15px; border: 1px solid #007bff; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_current_matches():
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    try: return requests.get(url).json().get('data', [])
    except: return []

@st.cache_data(ttl=3600)
def get_master_schedule():
    url = f"https://api.cricapi.com/v1/matches?apikey={API_KEY}&offset=0"
    try: return requests.get(url).json().get('data', [])
    except: return []

@st.cache_data(ttl=60)
def get_squad_details(match_id):
    url = f"https://api.cricapi.com/v1/match_squad?apikey={API_KEY}&id={match_id}"
    try:
        res = requests.get(url).json()
        all_players = []
        if res.get('status') == 'success':
            for team in res['data']:
                for p in team['players']:
                    all_players.append({
                        "name": p['name'],
                        "role": p.get('role', 'batsman').lower(),
                        "playing": p.get('status') == 'playing'
                    })
        return all_players
    except: return []

@st.cache_data(ttl=60)
def get_scorecard(match_id):
    if not match_id: return {}
    url = f"https://api.cricapi.com/v1/match_scorecard?apikey={API_KEY}&id={match_id}"
    try:
        res = requests.get(url).json()
        stats = {}
        if res.get('status') == 'success':
            for inning in res['data'].get('scorecard', []):
                for b in inning.get('batting', []):
                    stats[b['content']] = stats.get(b['content'], 0) + int(b.get('r', 0))
                for bo in inning.get('bowling', []):
                    stats[bo['content']] = stats.get(bo['content'], 0) + (int(bo.get('w', 0)) * 25)
        return stats
    except: return {}

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏆 League Rules")
    st.info("🧤 2 WK (Exactly)\n\n🏏 Max 6 Bat\n\n⚡ Min 1 AR\n\n🎾 Min 1 Bowl")
    st.divider()
    if st.button("🔄 Refresh All Data"):
        st.cache_data.clear()
        st.rerun()

# --- DEFINE TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.subheader("🏏 T20 World Cup & Series Finder")
    search_query = st.text_input("Search Series (e.g., 'World Cup', 'India'):", "World Cup").lower()
    
    live = get_current_matches()
    master = get_master_schedule()
    combined = {m['id']: m for m in (live + master)}.values()
    
    if combined:
        series_matches = [m for m in combined if search_query in m.get('name', '').lower()]
        series_matches = sorted(series_matches, key=lambda x: x['dateTimeGMT'])

        for m in series_matches:
            gmt_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
            ist_time = gmt_time + timedelta(hours=5, minutes=30)
            now = datetime.now(timezone.utc)
            diff = gmt_time - now
            
            # Filter: Show only if not older than 12 hours
            if diff.total_seconds() < -43200: continue

            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{m['name']}**")
                    st.caption(f"🗓️ IST: {ist_time.strftime('%d %b, %I:%M %p')}")
                    
                    if m.get('matchStarted'):
                        st.success(f"🏏 {m['status']}")
                    elif diff.total_seconds() > 0:
                        h, rem = divmod(int(diff.total_seconds()), 3600)
                        m_left, _ = divmod(rem, 60)
                        if diff.total_seconds() < 1800: st.error(f"🚨 LOCKING: {m_left}m left!")
                        else: st.warning(f"⏳ {h}h {m_left}m left")
                    else: st.info("🕒 Toss Time")

                with col2:
                    st.write("Match ID:")
                    st.code(m['id'])
                st.divider()

# --- TAB 2: CREATE TEAM ---
with tab2:
    st.subheader("📝 Join the Contest")
    m_id = st.text_input("Paste Match ID from Match Center:")
    if m_id:
        # Check start time again to lock form
        combined_all = {m['id']: m for m in (get_current_matches() + get_master_schedule())}
        m_info = combined_all.get(m_id)
        
        if m_info:
            gmt_start = dateutil.parser.isoparse(m_info['dateTimeGMT']).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= gmt_start or m_info.get('matchStarted'):
                st.error("🔒 Entry Denied: Submissions are closed for this match.")
            else:
                squad = get_squad_details(m_id)
                if squad:
                    df_sq = pd.DataFrame(squad)
                    with st.form("team_form"):
                        user_name = st.text_input("Your Name:")
                        
                        opts = [f"{p['name']} ({p['role']}) - {'✅ Playing' if p['playing'] else '❌ Sub'}" for _, p in df_sq.iterrows()]
                        sel = st.multiselect("Select 11 Players:", opts)
                        
                        names = [o.split(" (")[0] for o in sel]
                        roles = [df_sq[df_sq['name'] == n]['role'].values[0] for n in names]
                        wk, bat, ar, bowl = roles.count('wicketkeeper'), roles.count('batsman'), roles.count('allrounder'), roles.count('bowler')
                        
                        st.write(f"**Squad Balance:** 🧤WK: {wk}/2 | 🏏BAT: {bat}/6 | ⚡AR: {ar}/min1 | 🎾BOWL: {bowl}/min1")
                        
                        c = st.selectbox("Captain (2x):", names if names else ["Select 11 players"])
                        vc = st.selectbox("Vice-Captain (1.5x):", [n for n in names if n != c] if names else ["Select 11 players"])
                        
                        if st.form_submit_button("LOCK SQUAD"):
                            if len(sel) == 11 and wk == 2 and bat <= 6 and ar >= 1 and bowl >= 1:
                                row = pd.DataFrame([{"User": user_name, "Players": ",".join(names), "Captain": c, "ViceCaptain": vc, "MatchID": m_id}])
                                current = conn.read(spreadsheet=SHEET_URL)
                                conn.update(spreadsheet=SHEET_URL, data=pd.concat([current, row]))
                                st.balloons()
                                st.success("Your team has been locked into Google Sheets!")
                            else: st.error("❌ Invalid Team: Please check the squad rules in the sidebar!")

# --- TAB 3: STANDINGS ---
with tab3:
    st.subheader("🏆 Live Leaderboard")
    tid = st.text_input("Enter Match ID to Track Points:")
    if tid:
        pts_map = get_scorecard(tid)
        history = conn.read(spreadsheet=SHEET_URL)
        m_teams = history[history['MatchID'] == tid]
        if not m_teams.empty:
            results = []
            for _, r in m_teams.iterrows():
                total = sum(pts_map.get(p,0) * (2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))
                results.append({"Member": r['User'], "Points": total})
            st.dataframe(pd.DataFrame(results).sort_values("Points", ascending=False), use_container_width=True, hide_index=True)
        else: st.info("No teams submitted for this ID yet.")

# --- TAB 4: HISTORY ---
with tab4:
    st.subheader("📜 Hall of Fame")
    try:
        h_data = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if not h_data.empty:
            summary = []
            for mid in h_data['MatchID'].unique():
                h_pts = get_scorecard(mid)
                m_t = h_data[h_data['MatchID'] == mid]
                scr = [{"U": r['User'], "P": sum(h_pts.get(p,0)*(2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))} for _, r in m_t.iterrows()]
                if scr:
                    win = max(scr, key=lambda x: x['P'])
                    summary.append({"Match ID": mid, "Winner": win['U'], "Winning Score": win['P']})
            st.table(pd.DataFrame(summary))
            st.divider()
            st.subheader("📊 Series MVP Standings")
            st.bar_chart(pd.DataFrame(summary)['Winner'].value_counts())
    except: st.error("History could not be loaded. Ensure the Google Sheet is correctly shared.")
