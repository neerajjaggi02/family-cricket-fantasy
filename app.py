# app.py

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= CONFIG =================

st.set_page_config(page_title="ICC Fantasy League", layout="wide")

CRICAPI_KEY = st.secrets["CRICAPI_KEY"]
BASE_URL = "https://api.cricapi.com/v1"

conn = st.connection("gsheets", type=GSheetsConnection)

# ================= API HELPERS =================

@st.cache_data(ttl=300)
def get_series_list():
    url = f"{BASE_URL}/series"
    params = {"apikey": CRICAPI_KEY, "offset": 0}
    res = requests.get(url, params=params).json()
    if res.get("status") == "success":
        return res.get("data", [])
    return []


@st.cache_data(ttl=300)
def get_series_matches(series_id):
    url = f"{BASE_URL}/seriesMatches"
    params = {"apikey": CRICAPI_KEY, "id": series_id}
    res = requests.get(url, params=params).json()
    if res.get("status") == "success":
        return res.get("data", {}).get("matchList", [])
    return []


@st.cache_data(ttl=120)
def get_match_squad(match_id):
    url = f"{BASE_URL}/match_squad"
    params = {"apikey": CRICAPI_KEY, "id": match_id}
    res = requests.get(url, params=params).json()
    if res.get("status") == "success":
        return res.get("data", {})
    return {}


@st.cache_data(ttl=60)
def get_scorecard(match_id):
    url = f"{BASE_URL}/match_scorecard"
    params = {"apikey": CRICAPI_KEY, "id": match_id}
    res = requests.get(url, params=params).json()
    if res.get("status") == "success":
        return res.get("data", {})
    return {}

# ================= GOOGLE SHEETS =================

def load_teams():
    try:
        return conn.read(worksheet="teams")
    except:
        return pd.DataFrame(columns=["user_id","match_id","players","captain","vice_captain"])


def save_teams(df):
    conn.update(worksheet="teams", data=df)

# ================= FANTASY ENGINE =================

def calculate_points(player):
    points = 0
    points += int(player.get("runs", 0)) * 1
    points += int(player.get("wickets", 0)) * 25
    points += int(player.get("catches", 0)) * 8
    return points


def extract_stats(scorecard):
    stats = {}
    for inning in scorecard.get("scorecard", []):
        for batter in inning.get("batting", []):
            stats[batter["id"]] = {
                "runs": batter.get("runs", 0),
                "wickets": 0,
                "catches": 0
            }
        for bowler in inning.get("bowling", []):
            pid = bowler["id"]
            if pid not in stats:
                stats[pid] = {}
            stats[pid]["wickets"] = bowler.get("wickets", 0)
    return stats


def calculate_team_points(team_row, stats):
    total = 0
    players = team_row["players"].split(",")
    captain = team_row["captain"]
    vice = team_row["vice_captain"]

    for pid in players:
        pstat = stats.get(pid.strip(), {})
        pts = calculate_points(pstat)

        if pid.strip() == captain:
            pts *= 2
        elif pid.strip() == vice:
            pts *= 1.5

        total += pts

    return total

# ================= UI =================

tab1, tab2, tab3 = st.tabs(["🏏 ICC T20 WC", "📝 Create Team", "🏆 Leaderboard"])

# ================= TAB 1 =================

with tab1:
    st.header("Select ICC T20 World Cup")

    series_list = get_series_list()
    icc_series = [s for s in series_list if "ICC" in s.get("name","") and "T20" in s.get("name","")]

    if not icc_series:
        st.warning("ICC T20 series not found in free API tier.")
    else:
        series = st.selectbox("Choose Series", icc_series, format_func=lambda x: x["name"])
        matches = get_series_matches(series["id"])

        for m in matches:
            st.write(f"🏏 {m.get('name')}")
            st.caption(f"Match ID: {m.get('id')}")
            st.caption(f"Started: {m.get('matchStarted')}")
            st.divider()

# ================= TAB 2 =================

with tab2:
    st.header("Create Team")

    username = st.text_input("Username")
    match_id = st.text_input("Match ID")

    if match_id:
        squad_data = get_match_squad(match_id)

        if squad_data:
            team1 = squad_data.get("teamInfo", [])[0]
            team2 = squad_data.get("teamInfo", [])[1]

            st.subheader("Available Players")

            players = squad_data.get("players", [])
            player_options = {p["name"]: p["id"] for p in players}

            selected_players = st.multiselect("Select 11 Players", list(player_options.keys()))

            captain = st.selectbox("Select Captain", selected_players)
            vice = st.selectbox("Select Vice Captain", selected_players)

            match_started = squad_data.get("matchStarted", False)

            if match_started:
                st.error("Match already started. Team creation locked.")
            else:
                if st.button("Save Team"):
                    if len(selected_players) != 11:
                        st.error("Select exactly 11 players.")
                    else:
                        teams_df = load_teams()

                        new_row = pd.DataFrame([{
                            "user_id": username,
                            "match_id": match_id,
                            "players": ",".join([player_options[p] for p in selected_players]),
                            "captain": player_options[captain],
                            "vice_captain": player_options[vice]
                        }])

                        teams_df = pd.concat([teams_df, new_row], ignore_index=True)
                        save_teams(teams_df)

                        st.success("Team Saved!")

        else:
            st.warning("Squad not available yet (before toss).")

# ================= TAB 3 =================

with tab3:
    st.header("Leaderboard")

    match_id_lb = st.text_input("Match ID for Leaderboard")

    if st.button("Generate Leaderboard"):
        teams_df = load_teams()
        teams_df = teams_df[teams_df["match_id"] == match_id_lb]

        if teams_df.empty:
            st.warning("No teams found.")
        else:
            scorecard = get_scorecard(match_id_lb)
            stats = extract_stats(scorecard)

            leaderboard = []

            for _, row in teams_df.iterrows():
                pts = calculate_team_points(row, stats)
                leaderboard.append({"User": row["user_id"], "Points": pts})

            lb_df = pd.DataFrame(leaderboard).sort_values(by="Points", ascending=False)
            st.dataframe(lb_df, use_container_width=True)
