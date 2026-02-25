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

# Custom CSS for a clean, professional GUI
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; 
        background-color: #f0f2f6; 
        border-radius: 5px; 
        padding: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #007bff; color: white !important; }
    .match-card {
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #007bff;
        background-color: white;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_all_possible_matches():
    # Hits both Current and Master list to ensure future games are visible
    curr_url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
    mast_url = f"https://api.cricapi.com/v1/matches?apikey={API_KEY}&offset=0"
    try:
        c = requests.get(curr_url).json().get('data', [])
        m = requests.get(mast_url).json().get('data', [])
        combined = {match['id']: match for match in (c + m)}.values()
        return sorted(list(combined), key=lambda x: x['dateTimeGMT'])
    except: return []

@st.cache_data(ttl=60)
def get_squad_details(match_id):
    url = f"https://api.cricapi.com/v1/match_squad?apikey={API_KEY}&id={match_id}"
    try:
        res = requests.get(url).json()
        all_p = []
        if res.get('status') == 'success':
            for team in res['data']:
                for p in team['players']:
                    all_p.append({
                        "name": p['name'],
                        "role": p.get('role', 'batsman').lower(),
                        "playing": p.get('status') == 'playing'
                    })
        return all_p
    except: return []

@st.cache_data(ttl=60)
def get_scorecard(match_id):
    if not match_id: return {}
    url = f"https://api.cricapi.com/v1/match_scorecard?apikey={API_KEY}&id={match_id}"
    try:
        res = requests.get(url).json()
        stats = {}
        if res.get('status') == 'success' and res.get('data'):
            for inning in res['data'].get('scorecard', []):
                for b in inning.get('batting', []):
                    stats[b['content']] = stats.get(b['content'], 0) + int(b.get('r', 0))
                for bo in inning.get('bowling', []):
                    stats[bo['content']] = stats.get(bo['content'], 0) + (int(bo.get('w', 0)) * 25)
        return stats
    except: return {}

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏆 League Hub")
    st.info("🧤 2 WK Required\n\n🏏 Max 6 Bat\n\n⚡ Min 1 All-rounder\n\n🎾 Min 1 Bowler")
    st.divider()
    if st.button("🔄 Clear App Cache"):
        st.cache_data.clear()
        st.rerun()

# --- MAIN TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    st.subheader("🏏 Live & Upcoming Series")
    search_q = st.text_input("Filter Series (e.g., 'World Cup', 'India'):", "World Cup").lower()
    
    all_m = get_all_possible_matches()
    
    if all_m:
        filtered = [m for m in all_m if search_q in m.get('name', '').lower()]
        
        for m in filtered:
            gmt_t = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
            ist_t = gmt_t + timedelta(hours=5, minutes=30)
            now = datetime.now(timezone.utc)
            diff = gmt_t - now
            
            # Hide if ended more than 1 day ago
            if diff.total_seconds() < -86400: continue

            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"### {m['name']}")
                    st.write(f"📅 **IST:** {ist_t.strftime('%d %b, %I:%M %p')}")
                    st.caption(f"📍 {m.get('venue', 'Venue TBA')}")
                
                with c2:
                    if m.get('matchStarted'):
                        st.success(f"🏏 {m['status']}")
                    elif diff.total_seconds() > 0:
                        h, rem = divmod(int(diff.total_seconds()), 3600)
                        ml, _ = divmod(rem, 60)
                        if diff.total_seconds() < 1800: st.error(f"🚨 LOCKING: {ml}m left")
                        else: st.warning(f"⏳ {h}h {ml}m left")
                    else: st.info("🕒 Toss / Starting")

                with c3:
                    st.write("Match ID:")
                    st.code(m['id'])
                st.divider()
    else:
        st.warning("No matches found. Check your API key or connection.")

# --- TAB 2: CREATE TEAM ---
with tab2:
    st.subheader("📝 Build Your Team")
    mid_input = st.text_input("Enter Match ID from Match Center:")
    
    if mid_input:
        # Check deadline before showing form
        matches_list = get_all_possible_matches()
        m_info = next((m for m in matches_list if m['id'] == mid_input), None)
        
        if m_info:
            gmt_start = dateutil.parser.isoparse(m_info['dateTimeGMT']).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= gmt_start or m_info.get('matchStarted'):
                st.error("🔒 Entry Locked: The match has already started!")
            else:
                squad = get_squad_details(mid_input)
                if squad:
                    df_sq = pd.DataFrame(squad)
                    with st.form("team_entry"):
                        u_name = st.text_input("Family Member Name:")
                        
                        opts = [f"{p['name']} ({p['role']}) - {'✅ Playing' if p['playing'] else '❌ Sub'}" for _, p in df_sq.iterrows()]
                        sel = st.multiselect("Select 11 Players:", opts)
                        
                        names = [o.split(" (")[0] for o in sel]
                        roles = [df_sq[df_sq['name'] == n]['role'].values[0] for n in names]
                        wk, bat, ar, bowl = roles.count('wicketkeeper'), roles.count('batsman'), roles.count('allrounder'), roles.count('bowler')
                        
                        st.write(f"**Current Balance:** 🧤WK: {wk}/2 | 🏏BAT: {bat}/6 | ⚡AR: {ar}/min1 | 🎾BOWL: {bowl}/min1")
                        
                        cap = st.selectbox("Captain (2x):", names if names else ["Select 11"])
                        vcap = st.selectbox("Vice-Captain (1.5x):", [n for n in names if n != cap] if names else ["Select 11"])
                        
                        if st.form_submit_button("LOCK SQUAD"):
                            if len(sel) == 11 and wk == 2 and bat <= 6 and ar >= 1 and bowl >= 1:
                                new_row = pd.DataFrame([{"User": u_name, "Players": ",".join(names), "Captain": cap, "ViceCaptain": vcap, "MatchID": mid_input}])
                                existing = conn.read(spreadsheet=SHEET_URL)
                                conn.update(spreadsheet=SHEET_URL, data=pd.concat([existing, new_row]))
                                st.balloons()
                                st.success("Team saved successfully!")
                            else: st.error("❌ Rules Violation: Please check role counts and squad size (11).")

# --- TAB 3: STANDINGS ---
with tab3:
    st.subheader("🏆 Live Leaderboard")
    tid = st.text_input("Enter Match ID to View Standings:")
    if tid:
        p_map = get_scorecard(tid)
        hist = conn.read(spreadsheet=SHEET_URL)
        teams = hist[hist['MatchID'] == tid]
        if not teams.empty:
            results = []
            for _, r in teams.iterrows():
                scr = sum(p_map.get(p,0) * (2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))
                results.append({"Member": r['User'], "Points": scr})
            st.dataframe(pd.DataFrame(results).sort_values("Points", ascending=False), use_container_width=True, hide_index=True)
        else: st.info("No teams submitted for this Match ID.")

# --- TAB 4: HISTORY ---
with tab4:
    st.subheader("📜 Season History")
    try:
        hall = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if not hall.empty:
            summary = []
            for m in hall['MatchID'].unique():
                pts = get_scorecard(m)
                tms = hall[hall['MatchID'] == m]
                scores = [{"U": r['User'], "P": sum(pts.get(p,0)*(2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))} for _, r in tms.iterrows()]
                if scores:
                    winner = max(scores, key=lambda x: x['P'])
                    summary.append({"Match ID": m, "Winner": winner['U'], "Score": winner['P']})
            st.table(pd.DataFrame(summary))
            st.divider()
            st.subheader("📊 Season Win Count")
            st.bar_chart(pd.DataFrame(summary)['Winner'].value_counts())
    except: st.warning("History loading... Ensure your Google Sheet is shared correctly.")
