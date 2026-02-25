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

# Custom CSS for a better GUI
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; background-color: #007bff; color: white; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .match-card { border: 1px solid #e0e0e0; padding: 20px; border-radius: 15px; margin-bottom: 10px; background: white; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- SIDEBAR: RULES & BRANDING ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/5351/5351473.png", width=100)
    st.title("League Rules")
    st.markdown("""
    **Squad Requirements:**
    - 🏏 **11** Players Total
    - 🧤 **2** Wicketkeepers (Strict)
    - 🏏 **Max 6** Batsmen
    - ⚡ **Min 1** All-rounder
    - 🎾 **Min 1** Bowler
    
    **Multipliers:**
    - 🎖️ **Captain:** 2.0x
    - 🎖️ **Vice-Cap:** 1.5x
    """)
    st.divider()
    if st.button("🔄 Global Refresh"):
        st.cache_data.clear()
        st.rerun()

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_live_matches():
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
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

# --- DEFINE TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: UNIVERSAL MATCH FINDER ---
with tab1:
    st.header("🏏 T20 World Cup Match Center")
    search_query = st.text_input("Search Series:", "World Cup").lower() # Defaults to World Cup
    
    matches = get_live_matches()
    
    if matches:
        # Filter for the series
        series_matches = [m for m in matches if search_query in m.get('name', '').lower()]
        
        if series_matches:
            st.write(f"Showing {len(series_matches)} matches for '{search_query}':")
            for m in series_matches:
                # Time Calculations
                match_time_gmt = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
                match_time_ist = match_time_gmt + timedelta(hours=5, minutes=30)
                now = datetime.now(timezone.utc)
                diff = match_time_gmt - now
                
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.subheader(m['name'])
                        st.caption(f"📅 {match_time_ist.strftime('%d %b, %I:%M %p')} IST")
                        
                        # Status Logic
                        if m.get('matchStarted'):
                            st.success(f"🏏 Status: {m['status']}")
                        elif diff.total_seconds() > 0:
                            h, rem = divmod(int(diff.total_seconds()), 3600)
                            m_left, _ = divmod(rem, 60)
                            label = f"🚨 LOCKING: {m_left}m" if diff.total_seconds() < 1800 else f"⏳ {h}h {m_left}m left"
                            st.warning(label)
                        else:
                            st.info("🕒 Toss/Started")

                    with col2:
                        st.write("Match ID:")
                        st.code(m['id'])
                    st.divider()
        else:
            st.warning(f"No active matches found for '{search_query}'.")
    else:
        st.error("Could not fetch match data. Check your API key.")

# --- TAB 2: CREATE TEAM ---
with tab2:
    m_id_input = st.text_input("📍 Paste Match ID to Start Building:")
    if m_id_input:
        all_m = get_live_matches()
        m_info = next((m for m in all_m if m['id'] == m_id_input), None)
        
        if m_info:
            m_start_gmt = dateutil.parser.isoparse(m_info['dateTimeGMT']).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= m_start_gmt or m_info.get('matchStarted'):
                st.error("🔒 Entry Denied: The match has already started!")
            else:
                squad = get_squad_details(m_id_input)
                if squad:
                    df_sq = pd.DataFrame(squad)
                    with st.form("builder"):
                        name = st.text_input("Player (Family Member) Name:")
                        
                        opts = [f"{p['name']} ({p['role']}) - {'✅' if p['playing'] else '❌'}" for _, p in df_sq.iterrows()]
                        sel = st.multiselect("Select your 11:", opts)
                        
                        names_only = [o.split(" (")[0] for o in sel]
                        roles = [df_sq[df_sq['name'] == n]['role'].values[0] for n in names_only]
                        
                        wk, bat, ar, bowl = roles.count('wicketkeeper'), roles.count('batsman'), roles.count('allrounder'), roles.count('bowler')
                        
                        st.write(f"**Balance:** 🧤WK: {wk}/2 | 🏏BAT: {bat}/6 | ⚡AR: {ar}/min1 | 🎾BOWL: {bowl}/min1")
                        
                        c = st.selectbox("Captain (2x):", names_only)
                        vc = st.selectbox("Vice-Captain (1.5x):", [n for n in names_only if n != c])
                        
                        if st.form_submit_button("LOCK TEAM"):
                            if len(sel) == 11 and wk == 2 and bat <= 6 and ar >= 1 and bowl >= 1:
                                row = pd.DataFrame([{"User": name, "Players": ",".join(names_only), "Captain": c, "ViceCaptain": vc, "MatchID": m_id_input}])
                                current = conn.read(spreadsheet=SHEET_URL)
                                conn.update(spreadsheet=SHEET_URL, data=pd.concat([current, row]))
                                st.balloons()
                                st.success("Team saved to Google Sheets!")
                            else:
                                st.error("❌ Check Rules: Exactly 2 WK, 11 total, and min 1 AR/Bowl!")

# --- TAB 3: STANDINGS ---
with tab3:
    track_id = st.text_input("🏆 Enter Match ID for Live Scoreboard:")
    if track_id:
        pts = get_scorecard(track_id)
        data = conn.read(spreadsheet=SHEET_URL)
        teams = data[data['MatchID'] == track_id]
        if not teams.empty:
            res = []
            for _, r in teams.iterrows():
                total = sum(pts.get(p,0) * (2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))
                res.append({"Member": r['User'], "Points": total})
            st.dataframe(pd.DataFrame(res).sort_values("Points", ascending=False), use_container_width=True)
        else: st.info("No teams submitted for this ID.")

# --- TAB 4: HISTORY ---
with tab4:
    try:
        hist_data = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if not hist_data.empty:
            winners = []
            for mid in hist_data['MatchID'].unique():
                h_pts = get_scorecard(mid)
                h_teams = hist_data[hist_data['MatchID'] == mid]
                scr = [{"User": r['User'], "P": sum(h_pts.get(p,0)*(2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))} for _, r in h_teams.iterrows()]
                if scr:
                    w = max(scr, key=lambda x: x['P'])
                    winners.append({"MatchID": mid, "Winner": w['User'], "Score": w['P']})
            
            st.table(pd.DataFrame(winners))
            st.divider()
            st.subheader("🥇 Season Standings")
            st.bar_chart(pd.DataFrame(winners)['Winner'].value_counts())
    except: st.warning("Share your Google Sheet with the Service Account email to see history!")
