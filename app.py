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

# --- SIDEBAR: ALWAYS VISIBLE RULES ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/5351/5351473.png", width=80)
    st.header("🏆 League Rules")
    st.markdown("""
    **Squad Requirements:**
    - 🏏 **11** Players Total
    - 🧤 **2** Wicketkeepers (Strict)
    - 🏏 **Max 6** Batsmen
    - ⚡ **Min 1** All-rounder
    - 🎾 **Min 1** Bowler
    
    **Point System:**
    - 🏃 **Run:** 1 pt
    -  wickets **Wicket:** 25 pts
    - ⭐ **Captain:** 2.0x
    - 🎖️ **Vice-Cap:** 1.5x
    """)
    st.divider()
    if st.button("🔄 Refresh All Data"):
        st.cache_data.clear()
        st.rerun()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_all_matches():
    # Hits both Current and Master list to ensure future games like India vs Zim show up
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

# --- DEFINE TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📺 MATCH CENTER", "📝 CREATE TEAM", "🏆 STANDINGS", "📜 HISTORY"])

# --- TAB 1: MATCH CENTER ---
with tab1:
    search_q = st.text_input("🔍 Search Series or Team (e.g., 'India', 'World Cup'):", "").strip().lower()
    all_m = get_all_matches()
    
    if all_m:
        # Smart Filter
        filtered = [m for m in all_m if search_q in m.get('name', '').lower()] if search_q else all_m[:15]
        
        # Split logic
        now = datetime.now(timezone.utc)
        live_comp = []
        upcoming = []
        
        for m in filtered:
            match_time = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
            if m.get('matchStarted') or now > match_time:
                live_comp.append(m)
            else:
                upcoming.append(m)

        # ⏳ SECTION 1: UPCOMING
        st.header("📅 Upcoming Matches")
        if upcoming:
            for m in upcoming:
                gmt_t = dateutil.parser.isoparse(m['dateTimeGMT']).replace(tzinfo=timezone.utc)
                ist_t = gmt_t + timedelta(hours=5, minutes=30)
                diff = gmt_t - now
                
                with st.container():
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.subheader(m['name'])
                        st.write(f"⏰ IST: {ist_t.strftime('%d %b, %I:%M %p')}")
                    with c2:
                        h, rem = divmod(int(diff.total_seconds()), 3600)
                        ml, _ = divmod(rem, 60)
                        if diff.total_seconds() < 1800: st.error(f"🚨 LOCKING: {ml}m left")
                        else: st.warning(f"⏳ {h}h {ml}m left")
                    with c3:
                        st.write("Match ID:")
                        st.code(m['id'])
                    st.divider()
        else: st.info("No upcoming matches found for this search.")

        # 🏁 SECTION 2: LIVE / RECENT
        st.header("🏁 Live & Recent")
        if live_comp:
            for m in reversed(live_comp[-8:]):
                with st.expander(f"{m['name']} ({m['status']})"):
                    st.write(f"**Status:** {m['status']}")
                    st.code(f"Match ID: {m['id']}")
    else: st.error("No data found. Check your API key.")

# --- TAB 2: CREATE TEAM ---
with tab2:
    st.subheader("📝 Join the Match")
    mid = st.text_input("Enter Match ID from Match Center:")
    if mid:
        m_list = get_all_matches()
        m_info = next((m for m in m_list if m['id'] == mid), None)
        
        if m_info:
            gmt_start = dateutil.parser.isoparse(m_info['dateTimeGMT']).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= gmt_start or m_info.get('matchStarted'):
                st.error("🔒 Entry Denied: The match has already started!")
            else:
                squad = get_squad_details(mid)
                if squad:
                    df_sq = pd.DataFrame(squad)
                    with st.form("team_entry"):
                        u_name = st.text_input("Your Name:")
                        opts = [f"{p['name']} ({p['role']}) - {'✅ Playing' if p['playing'] else '❌ Sub'}" for _, p in df_sq.iterrows()]
                        sel = st.multiselect("Select 11 Players:", opts)
                        names = [o.split(" (")[0] for o in sel]
                        roles = [df_sq[df_sq['name'] == n]['role'].values[0] for n in names]
                        wk, bat, ar, bowl = roles.count('wicketkeeper'), roles.count('batsman'), roles.count('allrounder'), roles.count('bowler')
                        
                        st.write(f"**Squad Balance:** 🧤WK: {wk}/2 | 🏏BAT: {bat}/6 | ⚡AR: {ar}/min1 | 🎾BOWL: {bowl}/min1")
                        c = st.selectbox("Captain (2x):", names if names else ["Select 11"])
                        vc = st.selectbox("Vice-Captain (1.5x):", [n for n in names if n != c] if names else ["Select 11"])
                        
                        if st.form_submit_button("LOCK SQUAD"):
                            if len(sel) == 11 and wk == 2 and bat <= 6 and ar >= 1 and bowl >= 1:
                                row = pd.DataFrame([{"User": u_name, "Players": ",".join(names), "Captain": c, "ViceCaptain": vc, "MatchID": mid}])
                                curr_sheet = conn.read(spreadsheet=SHEET_URL)
                                conn.update(spreadsheet=SHEET_URL, data=pd.concat([curr_sheet, row]))
                                st.balloons()
                                st.success("Team saved successfully!")
                            else: st.error("❌ Rules Violation: Check 11 total and role counts.")

# --- TAB 3: STANDINGS ---
with tab3:
    st.subheader("🏆 Live Leaderboard")
    tid = st.text_input("Enter Match ID for Live Points:")
    if tid:
        p_map = get_scorecard(tid)
        hist = conn.read(spreadsheet=SHEET_URL)
        teams = hist[hist['MatchID'] == tid]
        if not teams.empty:
            res = [{"Member": r['User'], "Points": sum(p_map.get(p,0)*(2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))} for _, r in teams.iterrows()]
            st.dataframe(pd.DataFrame(res).sort_values("Points", ascending=False), use_container_width=True, hide_index=True)
        else: st.info("No teams submitted for this ID.")

# --- TAB 4: HISTORY ---
with tab4:
    st.subheader("📜 Hall of Fame")
    try:
        hall = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if not hall.empty:
            summary = []
            for m in hall['MatchID'].unique():
                pts = get_scorecard(m)
                tms = hall[hall['MatchID'] == m]
                scr = [{"U": r['User'], "P": sum(pts.get(p,0)*(2 if p==r['Captain'] else 1.5 if p==r['ViceCaptain'] else 1) for p in str(r['Players']).split(","))} for _, r in tms.iterrows()]
                if scr:
                    win = max(scr, key=lambda x: x['P'])
                    summary.append({"Match": m, "Winner": win['U'], "Score": win['P']})
            st.table(pd.DataFrame(summary))
    except: st.warning("Connect your sheet to see history.")
