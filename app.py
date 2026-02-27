# app.py

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= CONFIG =================

CRICAPI_KEY = "YOUR_CRICAPI_KEY"
BASE_URL = "https://api.cricapi.com/v1"

st.set_page_config(page_title="Fantasy Pro", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)

# ================= API FUNCTIONS =================

@st.cache_data(ttl=60)
def get_matches():
    url = f"{BASE_URL}/currentMatches?apikey={CRICAPI_KEY}&offset=0"
    res = requests.get(url).json()
    return res.get("data", [])


@st.cache_data(ttl=30)
def get_scorecard(match_id):
    url = f"{BASE_URL}/match_scorecard?apikey={CRICAPI_KEY}&id={match_id}"
    res = requests.get(url).json()
    return res.get("data", {})


# ================= FANTASY ENGINE =================

def calculate_points(player):
    points = 0
    points += player.get("runs", 0) * 1
    points += player.get("wickets", 0) * 25
    points += player.get("catches", 0) * 8
    points += player.get("fours", 0) * 1
    points += player.get("sixes", 0) * 2
    return points


def calculate_team_points(team_row, scorecard):
    total = 0
    players = team_row["players"].split(",")
    captain = team_row["captain"]
    vice = team_row["vice_captain"]

    for p in players:
        stats = scorecard.get(p, {})
        pts = calculate_points(stats)

        if p == captain:
            pts *= 2
        elif p == vice:
            pts *= 1.5

        total += pts

    return total


# ================= GOOGLE SHEETS HELPERS =================

def load_sheet(name):
    return conn.read(worksheet=name)


def save_sheet(name, df):
    conn.update(worksheet=name, data=df)


# ================= UI =================

tabs = st.tabs(["📺 Matches", "📝 Create Team", "🏆 Leaderboard"])

# ================= MATCH TAB =================

with tabs[0]:
    st.header("Live Matches")

    matches = get_matches()

    for m in matches:
        st.write(f"🏏 {m['name']}")
        st.caption(f"Match ID: {m['id']}")
        st.divider()


# ================= TEAM CREATION =================

with tabs[1]:
    st.header("Create Fantasy Team")

    username = st.text_input("Enter Username")
    match_id = st.text_input("Enter Match ID")

    players = st.text_area("Enter Player IDs (comma separated)")
    captain = st.text_input("Captain ID")
    vice = st.text_input("Vice Captain ID")

    if st.button("Save Team"):

        teams_df = load_sheet("teams")

        new_row = pd.DataFrame([{
            "user_id": username,
            "match_id": match_id,
            "players": players,
            "captain": captain,
            "vice_captain": vice
        }])

        teams_df = pd.concat([teams_df, new_row], ignore_index=True)
        save_sheet("teams", teams_df)

        st.success("Team Saved!")


# ================= LEADERBOARD =================

with tabs[2]:
    st.header("Leaderboard")

    match_id_lb = st.text_input("Enter Match ID to View Leaderboard")

    if st.button("Calculate Leaderboard"):

        teams_df = load_sheet("teams")
        teams_df = teams_df[teams_df["match_id"] == match_id_lb]

        scorecard = get_scorecard(match_id_lb)

        leaderboard = []

        for _, row in teams_df.iterrows():
            pts = calculate_team_points(row, scorecard)
            leaderboard.append({
                "user": row["user_id"],
                "points": pts
            })

        lb_df = pd.DataFrame(leaderboard)
        lb_df = lb_df.sort_values(by="points", ascending=False)

        st.dataframe(lb_df)
