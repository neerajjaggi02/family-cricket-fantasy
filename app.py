# app.py

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= CONFIG =================

st.set_page_config(page_title="Fantasy Cricket Pro", layout="wide")

CRICAPI_KEY = st.secrets["CRICAPI_KEY"]
GSHEET_URL = st.secrets["GSHEET_URL"]
BASE_URL = "https://api.cricapi.com/v1"

conn = st.connection("gsheets", type=GSheetsConnection)

# ================= SAFE API =================

def safe_api(endpoint, params):
    try:
        res = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
        if res.status_code != 200:
            return {}
        return res.json()
    except Exception:
        return {}

# ================= SHEET HELPERS =================

def load_sheet(name, columns=None):
    try:
        df = conn.read(spreadsheet=GSHEET_URL, worksheet=name)
        if df is None:
            return pd.DataFrame(columns=columns) if columns else pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame(columns=columns) if columns else pd.DataFrame()


def save_sheet(name, df):
    try:
        conn.update(spreadsheet=GSHEET_URL, worksheet=name, data=df)
    except Exception as e:
        st.error(f"Sheet write error: {e}")

# ================= ADMIN CACHE =================

def fetch_and_cache_matches():
    data = safe_api("matches", {"apikey": CRICAPI_KEY, "offset": 0})

    if data.get("status") != "success":
        st.error("API failed while fetching matches.")
        return

    matches = data.get("data", [])

    if not matches:
        st.warning("No matches returned from API.")
        return

    df = pd.DataFrame(
        [
            {
                "match_id": m.get("id"),
                "series_id": m.get("series_id"),
                "name": m.get("name"),
                "status": m.get("status"),
                "matchStarted": m.get("matchStarted"),
                "matchEnded": m.get("matchEnded"),
                "date": m.get("date"),
                "last_updated": datetime.utcnow(),
            }
            for m in matches
        ]
    )

    save_sheet("matches_cache", df)
    st.success(f"{len(df)} matches cached successfully.")


def fetch_and_cache_squad(match_id):

    data = safe_api("match_squad", {
        "apikey": CRICAPI_KEY,
        "id": match_id
    })

    if data.get("status") != "success":
        st.error("API failed while fetching squad.")
        return

    squad_data = data.get("data")

    if not squad_data:
        st.error("No squad data returned.")
        return

    squad_list = squad_data.get("squad", [])

    if not squad_list:
        st.warning("Squad not available for this match.")
        return

    rows = []

    for team in squad_list:
        team_name = team.get("team")
        players = team.get("players", [])

        for player in players:
            rows.append({
                "match_id": match_id,
                "team": team_name,
                "player_id": player.get("id"),
                "player_name": player.get("name"),
                "playing11": False
            })

    df = pd.DataFrame(rows)

    save_sheet("squad_cache", df)

    st.success("Squad cached successfully.")

# ================= UI =================

tab1, tab2, tab3 = st.tabs(
    ["🔎 Search Matches", "📝 Create Team", "🏆 Leaderboard"]
)

# ================= TAB 1 =================

with tab1:
    st.header("Search Series or Matches")

    if st.button("🔄 Admin Refresh Matches", key="refresh_matches"):
        fetch_and_cache_matches()

    matches_df = load_sheet("matches_cache")

    search = st.text_input("Search by Country, Team or Series", key="search_box")

    if not matches_df.empty:

        matches_df["search_blob"] = (
            matches_df["name"].astype(str) + " " +
            matches_df["status"].astype(str)
        )

        if search:
            filtered = matches_df[
                matches_df["search_blob"]
                .str.contains(search, case=False, na=False)
            ]
        else:
            filtered = matches_df

        if not filtered.empty:
            selected_match = st.selectbox(
                "Select Match",
                filtered["name"].tolist(),
                key="match_select"
            )

            match_id = filtered[
                filtered["name"] == selected_match
            ]["match_id"].values[0]

            st.success(f"Selected Match ID: {match_id}")
            st.session_state["selected_match_id"] = match_id

        else:
            st.warning("No matches found.")
    else:
        st.warning("No matches cached. Click Admin Refresh.")

# ================= TAB 2 =================

with tab2:
    st.header("Create Team")

    username = st.text_input("Username", key="username_input")
   match_id = st.session_state.get("selected_match_id")

if not match_id:
    st.warning("Select a match from Search tab first.")

    if match_id:

        if st.button("🔄 Fetch Squad (Admin)", key="fetch_squad"):
            fetch_and_cache_squad(match_id)
            st.success("Squad Cached")

        squad_df = load_sheet(
            "squad_cache",
            ["match_id", "player_id", "player_name", "playing11"],
        )

        match_squad = squad_df[squad_df["match_id"] == match_id]

        if not match_squad.empty:

            player_map = dict(
                zip(match_squad["player_name"], match_squad["player_id"])
            )

            selected = st.multiselect(
                "Select 11 Players",
                list(player_map.keys()),
                key="player_select",
            )

            captain = st.selectbox("Captain", selected, key="captain_select")
            vice = st.selectbox("Vice Captain", selected, key="vice_select")

            st.subheader("Playing XI")

            for _, row in match_squad.iterrows():
                if row["playing11"]:
                    st.write(f"🟢 {row['player_name']}")
                else:
                    st.write(f"🔴 {row['player_name']}")

            matches_df = load_sheet("matches_cache", [])
            started = matches_df[
                matches_df["match_id"] == match_id
            ]["matchStarted"].values

            if len(started) > 0 and started[0] is True:
                st.error("Match already started. Team locked.")
            else:
                if st.button("Save Team", key="save_team"):
                    if len(selected) != 11:
                        st.error("Select exactly 11 players.")
                    else:
                        teams_df = load_sheet(
                            "teams",
                            [
                                "user_id",
                                "match_id",
                                "contest_id",
                                "players",
                                "captain",
                                "vice_captain",
                            ],
                        )

                        new_row = pd.DataFrame(
                            [
                                {
                                    "user_id": username,
                                    "match_id": match_id,
                                    "contest_id": "default",
                                    "players": ",".join(
                                        [player_map[p] for p in selected]
                                    ),
                                    "captain": player_map[captain],
                                    "vice_captain": player_map[vice],
                                }
                            ]
                        )

                        teams_df = pd.concat(
                            [teams_df, new_row], ignore_index=True
                        )
                        save_sheet("teams", teams_df)

                        st.success("Team Saved")
        else:
            st.warning("No squad cached. Ask admin to fetch squad.")

# ================= TAB 3 =================

with tab3:
    st.header("Leaderboard")

    match_id_lb = st.text_input("Match ID", key="leaderboard_match")

    if st.button("Generate Leaderboard", key="generate_lb"):

        teams_df = load_sheet("teams", [])
        filtered = teams_df[teams_df["match_id"] == match_id_lb]

        if filtered.empty:
            st.warning("No teams found.")
        else:
            leaderboard = []

            for _, row in filtered.iterrows():
                player_count = len(row["players"].split(","))
                leaderboard.append(
                    {"User": row["user_id"], "Points": player_count * 10}
                )

            lb = pd.DataFrame(leaderboard).sort_values(
                by="Points", ascending=False
            )
            st.dataframe(lb, use_container_width=True)
