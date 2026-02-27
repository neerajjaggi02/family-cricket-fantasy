# app.py

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone
from streamlit_gsheets import GSheetsConnection

# ================= CONFIG =================

st.set_page_config(page_title="Fantasy ICC League", layout="wide")

CRICAPI_KEY = st.secrets["CRICAPI_KEY"]
BASE_URL = "https://api.cricapi.com/v1"

conn = st.connection("gsheets", type=GSheetsConnection)

# ================= SAFE API =================

def safe_api_call(endpoint, params):
    try:
        res = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
        if res.status_code != 200:
            return {}
        try:
            return res.json()
        except:
            return {}
    except:
        return {}

# ================= SERIES =================

@st.cache_data(ttl=600)
def get_active_icc_t20_series():
    data = safe_api_call("series", {"apikey": CRICAPI_KEY, "offset": 0})
    if data.get("status") != "success":
        return []

    today = datetime.utcnow().date()
    active = []

    for s in data.get("data", []):
        name = s.get("name", "")

        if "ICC" in name and "T20" in name and "Women" not in name:
            try:
                start = datetime.strptime(s["startDate"], "%Y-%m-%d").date()
                end = datetime.strptime(s["endDate"], "%Y-%m-%d").date()

                if end >= today:
                    active.append(s)
            except:
                continue

    return active

@st.cache_data(ttl=300)
def get_series_matches(series_id):
    data = safe_api_call("seriesMatches", {
        "apikey": CRICAPI_KEY,
        "id": series_id
    })
    if data.get("status") != "success":
        return []
    return data.get("data", {}).get("matchList", [])

# ================= MATCH DATA =================

@st.cache_data(ttl=120)
def get_match_squad(match_id):
    data = safe_api_call("match_squad", {
        "apikey": CRICAPI_KEY,
        "id": match_id
    })
    if data.get("status") == "success":
        return data.get("data", {})
    return {}

@st.cache_data(ttl=60)
def get_scorecard(match_id):
    data = safe_api_call("match_scorecard", {
        "apikey": CRICAPI_KEY,
        "id": match_id
    })
    if data.get("status") == "success":
        return data.get("data", {})
    return {}

# ================= GOOGLE SHEETS =================

def load_sheet(name, columns):
    try:
        return conn.read(worksheet=name)
    except:
        return pd.DataFrame(columns=columns)

def save_sheet(name, df):
    conn.update(worksheet=name, data=df)

# ================= FANTASY ENGINE =================

def calculate_points(player):
    return (
        int(player.get("runs", 0)) * 1 +
        int(player.get("wickets", 0)) * 25 +
        int(player.get("catches", 0)) * 8
    )

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

def calculate_team_points(row, stats):
    total = 0
    players = row["players"].split(",")
    for pid in players:
        pts = calculate_points(stats.get(pid.strip(), {}))
        if pid.strip() == row["captain"]:
            pts *= 2
        elif pid.strip() == row["vice_captain"]:
            pts *= 1.5
        total += pts
    return total

# ================= UI =================

tab1, tab2, tab3 = st.tabs(["🏏 Active ICC T20", "📝 Create Team", "🏆 Leaderboard"])

# ================= TAB 1 =================

with tab1:
    st.header("Active ICC Men's T20 Series")

    series_list = get_active_icc_t20_series()

    if not series_list:
        st.warning("No active ICC T20 series found.")
    else:
        series = st.selectbox(
            "Select Series",
            series_list,
            format_func=lambda x: x["name"],
            key="series_select"
        )

        matches = get_series_matches(series["id"])

        for m in matches:
            st.write(f"🏏 {m['name']}")
            st.caption(f"Match ID: {m['id']}")
            st.caption(f"Started: {m.get('matchStarted')}")
            st.divider()

# ================= TAB 2 =================

with tab2:
    st.header("Create Team & Join Contest")

    username = st.text_input("Username", key="username_input")
    match_id = st.text_input("Match ID", key="create_match_id")

    contests_df = load_sheet("contests", ["contest_id","match_id","contest_name"])
    teams_df = load_sheet("teams", ["user_id","match_id","contest_id","players","captain","vice_captain"])

    if match_id:
        squad = get_match_squad(match_id)

        if squad:
            players = squad.get("players", [])
            playing_xi = squad.get("playing11", [])

            player_map = {p["name"]: p["id"] for p in players}

            selected = st.multiselect(
                "Select 11 Players",
                list(player_map.keys()),
                key="player_multiselect"
            )

            captain = st.selectbox(
                "Captain",
                selected,
                key="captain_select"
            )

            vice = st.selectbox(
                "Vice Captain",
                selected,
                key="vice_select"
            )

            st.subheader("Playing XI Status")

            for p in players:
                name = p["name"]
                if name in playing_xi:
                    st.write(f"🟢 {name}")
                else:
                    st.write(f"🔴 {name}")

            match_started = squad.get("matchStarted") is True

            if match_started:
                st.error("Match already started. Joining locked.")
            else:
                contest_name = st.text_input("Contest Name", key="contest_name_input")

                if st.button("Create / Join Contest", key="join_contest_btn"):
                    if len(selected) != 11:
                        st.error("Select exactly 11 players.")
                    else:
                        contest_id = f"{match_id}_{contest_name}"

                        if contest_id not in contests_df["contest_id"].values:
                            new_contest = pd.DataFrame([{
                                "contest_id": contest_id,
                                "match_id": match_id,
                                "contest_name": contest_name
                            }])
                            contests_df = pd.concat([contests_df, new_contest], ignore_index=True)
                            save_sheet("contests", contests_df)

                        new_team = pd.DataFrame([{
                            "user_id": username,
                            "match_id": match_id,
                            "contest_id": contest_id,
                            "players": ",".join([player_map[p] for p in selected]),
                            "captain": player_map[captain],
                            "vice_captain": player_map[vice]
                        }])

                        teams_df = pd.concat([teams_df, new_team], ignore_index=True)
                        save_sheet("teams", teams_df)

                        st.success("Joined Contest Successfully!")

# ================= TAB 3 =================

with tab3:
    st.header("Contest Leaderboard")

    match_id_lb = st.text_input("Match ID", key="leaderboard_match_id")
    contest_id_lb = st.text_input("Contest ID", key="leaderboard_contest_id")

    if st.button("Generate Leaderboard", key="leaderboard_btn"):
        teams_df = load_sheet("teams", [])

        filtered = teams_df[
            (teams_df["match_id"] == match_id_lb) &
            (teams_df["contest_id"] == contest_id_lb)
        ]

        if filtered.empty:
            st.warning("No entries.")
        else:
            scorecard = get_scorecard(match_id_lb)
            stats = extract_stats(scorecard)

            leaderboard = []

            for _, row in filtered.iterrows():
                pts = calculate_team_points(row, stats)
                leaderboard.append({
                    "User": row["user_id"],
                    "Points": pts
                })

            lb = pd.DataFrame(leaderboard).sort_values(by="Points", ascending=False)
            st.dataframe(lb, use_container_width=True)
