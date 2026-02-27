# app.py

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= CONFIG =================

st.set_page_config(page_title="Fantasy Cricket Pro", layout="wide")

CRICAPI_KEY = st.secrets["CRICAPI_KEY"]
RAPID_API_KEY = st.secrets["RAPID_API_KEY"]
GSHEET_URL = st.secrets["GSHEET_URL"]

CRIC_BASE = "https://api.cricapi.com/v1"
RAPID_HOST = "cricket-api-free-data.p.rapidapi.com"

conn = st.connection("gsheets", type=GSheetsConnection)

# ================= HELPERS =================

def safe_api(url, headers=None, params=None):
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code != 200:
            return {}
        return res.json()
    except Exception:
        return {}

def load_sheet(name):
    try:
        df = conn.read(spreadsheet=GSHEET_URL, worksheet=name)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def save_sheet(name, df):
    conn.update(spreadsheet=GSHEET_URL, worksheet=name, data=df)

# ================= MATCH CACHE =================

def fetch_matches():

    url = f"{CRIC_BASE}/matches"
    data = safe_api(url, params={"apikey": CRICAPI_KEY, "offset": 0})

    if data.get("status") != "success":
        st.error("Failed to fetch matches.")
        return

    rows = []

    for m in data.get("data", []):
        team_info = m.get("teamInfo", [])

        if len(team_info) >= 2:
            team1_id = team_info[0].get("id")
            team2_id = team_info[1].get("id")
        else:
            continue

        rows.append({
            "match_id": m.get("id"),
            "name": m.get("name"),
            "status": m.get("status"),
            "team1_id": team1_id,
            "team2_id": team2_id,
            "locked": False,
            "last_updated": datetime.utcnow()
        })

    df = pd.DataFrame(rows)
    save_sheet("matches_cache", df)
    st.success("Matches cached.")

# ================= SQUAD FETCH (RAPIDAPI) =================

def fetch_team_players(team_id):

    url = f"https://{RAPID_HOST}/cricket-players"

    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": RAPID_HOST
    }

    data = safe_api(url, headers=headers, params={"teamid": team_id})
    return data.get("data", [])

def fetch_match_squad(match_row):

    players_all = []

    for team_id in [match_row["team1_id"], match_row["team2_id"]]:

        players = fetch_team_players(team_id)

        for p in players:
            players_all.append({
                "match_id": match_row["match_id"],
                "team_id": team_id,
                "player_id": p.get("id"),
                "player_name": p.get("name"),
                "playing11": False
            })

    if players_all:
        df = pd.DataFrame(players_all)
        save_sheet("squad_cache", df)
        st.success("Squad cached from RapidAPI.")
    else:
        st.warning("No players returned.")

# ================= UI =================

tab1, tab2, tab3 = st.tabs(
    ["🔎 Search Matches", "🛠 Admin Panel", "📝 Create Team"]
)

# ================= TAB 1 =================

with tab1:

    if st.button("🔄 Refresh Matches"):
        fetch_matches()

    matches_df = load_sheet("matches_cache")

    search = st.text_input("Search Match")

    if not matches_df.empty:

        if search:
            filtered = matches_df[
                matches_df["name"].str.contains(search, case=False, na=False)
            ]
        else:
            filtered = matches_df

        if not filtered.empty:

            selected = st.selectbox("Select Match", filtered["name"])

            match_row = filtered[filtered["name"] == selected].iloc[0]

            st.session_state["selected_match"] = match_row

            st.success("Match selected.")

# ================= TAB 2 (ADMIN) =================

with tab2:

    st.subheader("Admin Controls")

    match_row = st.session_state.get("selected_match")

    if match_row is None:
        st.warning("Select match first.")
    else:

        if st.button("Fetch Squad from RapidAPI"):
            fetch_match_squad(match_row)

        squad_df = load_sheet("squad_cache")

        match_squad = squad_df[
            squad_df["match_id"] == match_row["match_id"]
        ]

        if not match_squad.empty:

            st.write("Set Playing XI")

            for i, row in match_squad.iterrows():
                is_playing = st.checkbox(
                    row["player_name"],
                    value=row["playing11"],
                    key=f"xi_{i}"
                )
                squad_df.at[i, "playing11"] = is_playing

            if st.button("Save Playing XI"):
                save_sheet("squad_cache", squad_df)
                st.success("Playing XI updated.")

        matches_df = load_sheet("matches_cache")

        if st.button("Toggle Lock Match"):
            current_lock = match_row["locked"]
            matches_df.loc[
                matches_df["match_id"] == match_row["match_id"],
                "locked"
            ] = not current_lock

            save_sheet("matches_cache", matches_df)
            st.success("Match lock toggled.")

# ================= TAB 3 =================

with tab3:

    st.subheader("Create Fantasy Team")

    username = st.text_input("Username")

    match_row = st.session_state.get("selected_match")

    if match_row is None:
        st.warning("Select match first.")
    else:

        matches_df = load_sheet("matches_cache")

        locked = matches_df[
            matches_df["match_id"] == match_row["match_id"]
        ]["locked"].values[0]

        if locked:
            st.error("Match locked. Cannot join.")
        else:

            squad_df = load_sheet("squad_cache")

            match_squad = squad_df[
                squad_df["match_id"] == match_row["match_id"]
            ]

            if match_squad.empty:
                st.warning("Squad not available.")
            else:

                player_list = match_squad["player_name"].tolist()

                selected = st.multiselect("Select 11 Players", player_list)

                if st.button("Save Team"):

                    if len(selected) != 11:
                        st.error("Select exactly 11 players.")
                    else:

                        teams_df = load_sheet("teams")

                        new_row = pd.DataFrame([{
                            "user": username,
                            "match_id": match_row["match_id"],
                            "players": ",".join(selected)
                        }])

                        teams_df = pd.concat([teams_df, new_row], ignore_index=True)

                        save_sheet("teams", teams_df)

                        st.success("Team saved.")
