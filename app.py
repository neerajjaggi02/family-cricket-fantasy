# app.py

import streamlit as st
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# ================= CONFIG =================

st.set_page_config(page_title="Fantasy Cricket Pro", layout="wide")

CRICAPI_KEY = st.secrets["CRICAPI_KEY"]
BASE_URL = "https://api.cricapi.com/v1"

conn = st.connection("gsheets", type=GSheetsConnection)

# ================= API FUNCTIONS =================

@st.cache_data(ttl=60)
def get_all_matches():
    url = f"{BASE_URL}/currentMatches"
    params = {
        "apikey": CRICAPI_KEY,
        "offset": 0
    }

    try:
        res = requests.get(url, params=params)
        data = res.json()

        if data.get("status") != "success":
            return []

        return data.get("data", [])
    except Exception:
        return []


@st.cache_data(ttl=30)
def get_scorecard(match_id):
    url = f"{BASE_URL}/match_scorecard"
    params = {
        "apikey": CRICAPI_KEY,
        "id": match_id
    }

    try:
        res = requests.get(url, params=params)
        data = res.json()

        if data.get("status") != "success":
            return {}

        return data.get("data", {})
    except Exception:
        return {}

# ================= FANTASY ENGINE =================

def calculate_points(player_stats):
    points = 0

    runs = int(player_stats.get("runs", 0))
    wickets = int(player_stats.get("wickets", 0))
    catches = int(player_stats.get("catches", 0))
    fours = int(player_stats.get("fours", 0))
    sixes = int(player_stats.get("sixes", 0))

    points += runs * 1
    points += wickets * 25
    points += catches * 8
    points += fours * 1
    points += sixes * 2

    return points


def extract_player_stats(scorecard):
    player_map = {}

    try:
        innings = scorecard.get("scorecard", [])

        for inning in innings:
            for batter in inning.get("batting", []):
                player_map[batter.get("id")] = {
                    "runs": batter.get("runs", 0),
                    "fours": batter.get("fours", 0),
                    "sixes": batter.get("sixes", 0),
                    "wickets": 0,
                    "catches": 0
                }

            for bowler in inning.get("bowling", []):
                pid = bowler.get("id")
                if pid not in player_map:
                    player_map[pid] = {}

                player_map[pid]["wickets"] = bowler.get("wickets", 0)

    except Exception:
        pass

    return player_map


def calculate_team_points(team_row, player_stats):
    total = 0

    players = team_row["players"].split(",")
    captain = team_row["captain"]
    vice = team_row["vice_captain"]

    for pid in players:
        stats = player_stats.get(pid.strip(), {})
        pts = calculate_points(stats)

        if pid.strip() == captain:
            pts *= 2
        elif pid.strip() == vice:
            pts *= 1.5

        total += pts

    return total

# ================= GOOGLE SHEET HELPERS =================

def load_teams():
    try:
        return conn.read(worksheet="teams")
    except Exception:
        return pd.DataFrame(columns=[
            "user_id", "match_id", "players", "captain", "vice_captain"
        ])


def save_teams(df):
    conn.update(worksheet="teams", data=df)

# ================= UI =================

tab1, tab2, tab3 = st.tabs(["📺 Matches", "📝 Create Team", "🏆 Leaderboard"])

# ================= MATCHES =================

with tab1:
    st.header("🏏 Live & Upcoming Matches")

    matches = get_all_matches()

    if not matches:
        st.warning("No matches found or API limit reached.")

    live = [m for m in matches if m.get("matchStarted") and not m.get("matchEnded")]
    upcoming = [m for m in matches if not m.get("matchStarted")]

    st.subheader("🔥 Live Matches")
    for m in live:
        st.write(f"🏏 {m.get('name')}")
        st.caption(f"Match ID: {m.get('id')}")
        st.divider()

    st.subheader("📅 Upcoming Matches")
    for m in upcoming:
        st.write(f"🏏 {m.get('name')}")
        st.caption(f"Match ID: {m.get('id')}")
        st.divider()

# ================= CREATE TEAM =================

with tab2:
    st.header("Create Fantasy Team")

    username = st.text_input("Username")
    match_id = st.text_input("Match ID")
    players = st.text_area("Player IDs (comma separated)")
    captain = st.text_input("Captain ID")
    vice = st.text_input("Vice Captain ID")

    if st.button("Save Team"):

        if not all([username, match_id, players, captain, vice]):
            st.error("All fields are required.")
        else:
            teams_df = load_teams()

            new_row = pd.DataFrame([{
                "user_id": username,
                "match_id": match_id,
                "players": players,
                "captain": captain,
                "vice_captain": vice
            }])

            teams_df = pd.concat([teams_df, new_row], ignore_index=True)
            save_teams(teams_df)

            st.success("Team saved successfully!")

# ================= LEADERBOARD =================

with tab3:
    st.header("🏆 Match Leaderboard")

    match_id_lb = st.text_input("Enter Match ID")

    if st.button("Generate Leaderboard"):

        teams_df = load_teams()
        teams_df = teams_df[teams_df["match_id"] == match_id_lb]

        if teams_df.empty:
            st.warning("No teams found for this match.")
        else:
            scorecard = get_scorecard(match_id_lb)
            player_stats = extract_player_stats(scorecard)

            leaderboard = []

            for _, row in teams_df.iterrows():
                pts = calculate_team_points(row, player_stats)
                leaderboard.append({
                    "User": row["user_id"],
                    "Points": round(pts, 2)
                })

            lb_df = pd.DataFrame(leaderboard)
            lb_df = lb_df.sort_values(by="Points", ascending=False)

            st.dataframe(lb_df, use_container_width=True)
