# app.py

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Fantasy League Pro", layout="wide")

CRICAPI_KEY = st.secrets["CRICAPI_KEY"]
BASE_URL = "https://api.cricapi.com/v1"
conn = st.connection("gsheets", type=GSheetsConnection)

# ================= SAFE API =================

def safe_api(endpoint, params):
    try:
        res = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
        if res.status_code == 200:
            return res.json()
        return {}
    except:
        return {}

# ================= SHEET HELPERS =================

def load_sheet(name, cols):
    try:
        return conn.read(worksheet=name)
    except:
        return pd.DataFrame(columns=cols)

def save_sheet(name, df):
    conn.update(worksheet=name, data=df)

# ================= ADMIN FETCH =================

def fetch_and_cache_matches():
    data = safe_api("currentMatches", {
        "apikey": CRICAPI_KEY,
        "offset": 0
    })

    if data.get("status") != "success":
        return

    matches = data.get("data", [])

    df = pd.DataFrame([{
        "match_id": m["id"],
        "series": m.get("series"),
        "name": m["name"],
        "matchStarted": m.get("matchStarted"),
        "last_updated": datetime.utcnow()
    } for m in matches])

    save_sheet("matches_cache", df)

def fetch_and_cache_squad(match_id):
    data = safe_api("match_squad", {
        "apikey": CRICAPI_KEY,
        "id": match_id
    })

    if data.get("status") != "success":
        return

    squad = data.get("data", {})
    players = squad.get("players", [])
    playing_xi = squad.get("playing11", [])

    df = pd.DataFrame([{
        "match_id": match_id,
        "player_id": p["id"],
        "player_name": p["name"],
        "playing11": p["name"] in playing_xi
    } for p in players])

    save_sheet("squad_cache", df)

# ================= UI =================

tab1, tab2, tab3 = st.tabs(["🔎 Search Matches", "📝 Create Team", "🏆 Leaderboard"])

# ================= TAB 1 SEARCH =================

with tab1:
    st.header("Search Series or Matches")

    if st.button("🔄 Admin Refresh Matches"):
        fetch_and_cache_matches()
        st.success("Matches Updated")

    matches_df = load_sheet("matches_cache", 
        ["match_id","series","name","matchStarted","last_updated"])

    search = st.text_input("Search by Series or Match Name", key="search_box")

    if not matches_df.empty:
        filtered = matches_df[
            matches_df["series"].str.contains(search, case=False, na=False) |
            matches_df["name"].str.contains(search, case=False, na=False)
        ]

        st.dataframe(filtered)

# ================= TAB 2 CREATE TEAM =================

with tab2:
    st.header("Create Team")

    username = st.text_input("Username", key="username")
    match_id = st.text_input("Match ID", key="match_id_create")

    squad_df = load_sheet("squad_cache",
        ["match_id","player_id","player_name","playing11"])

    if match_id:

        if st.button("🔄 Fetch Squad (Admin Only)"):
            fetch_and_cache_squad(match_id)
            st.success("Squad Cached")

        match_squad = squad_df[squad_df["match_id"] == match_id]

        if not match_squad.empty:

            player_map = dict(zip(
                match_squad["player_name"],
                match_squad["player_id"]
            ))

            selected = st.multiselect(
                "Select 11 Players",
                list(player_map.keys()),
                key="player_select"
            )

            captain = st.selectbox("Captain", selected, key="captain")
            vice = st.selectbox("Vice Captain", selected, key="vice")

            st.subheader("Playing XI Status")

            for _, row in match_squad.iterrows():
                if row["playing11"]:
                    st.write(f"🟢 {row['player_name']}")
                else:
                    st.write(f"🔴 {row['player_name']}")

            match_info = load_sheet("matches_cache", [])
            started = match_info[
                match_info["match_id"] == match_id
            ]["matchStarted"].values

            if len(started) > 0 and started[0]:
                st.error("Match Started. Team Locked.")
            else:
                if st.button("Save Team"):
                    if len(selected) != 11:
                        st.error("Select 11 players")
                    else:
                        teams_df = load_sheet("teams", 
                            ["user_id","match_id","contest_id","players","captain","vice_captain"])

                        new_row = pd.DataFrame([{
                            "user_id": username,
                            "match_id": match_id,
                            "contest_id": "default",
                            "players": ",".join([player_map[p] for p in selected]),
                            "captain": player_map[captain],
                            "vice_captain": player_map[vice]
                        }])

                        teams_df = pd.concat([teams_df, new_row], ignore_index=True)
                        save_sheet("teams", teams_df)

                        st.success("Team Saved")

        else:
            st.warning("No squad cached. Ask admin to fetch squad.")

# ================= TAB 3 =================

with tab3:
    st.header("Leaderboard")

    match_id_lb = st.text_input("Match ID", key="lb_match")

    if st.button("Generate Leaderboard"):

        teams_df = load_sheet("teams", [])
        squad_df = load_sheet("squad_cache", [])

        filtered = teams_df[teams_df["match_id"] == match_id_lb]

        if filtered.empty:
            st.warning("No teams found")
        else:
            leaderboard = []

            for _, row in filtered.iterrows():
                total = 0
                players = row["players"].split(",")

                for pid in players:
                    if pid in squad_df["player_id"].values:
                        total += 10  # demo static points

                leaderboard.append({
                    "User": row["user_id"],
                    "Points": total
                })

            lb = pd.DataFrame(leaderboard).sort_values(by="Points", ascending=False)
            st.dataframe(lb)
