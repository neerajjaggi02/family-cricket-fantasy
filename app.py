import streamlit as st
import requests
import pandas as pd

# --- CONFIGURATION ---
API_KEY = "97efb164-e552-4332-93a8-60aaaefe0f1d"
# Update these names to match your family/friends
FAMILY_TEAMS = {
    "Dad's Dynamic XI": ["Virat Kohli", "Jasprit Bumrah", "KL Rahul"],
    "Aryan's Avengers": ["Hardik Pandya", "Virat Kohli", "Rashid Khan"],
    "Sneha's Stars": ["Jasprit Bumrah", "Hardik Pandya", "Rohit Sharma"],
    "Uncle's United": ["Rohit Sharma", "Virat Kohli", "Mohammed Shami"]
}

st.set_page_config(page_title="Family Fantasy League", page_icon="🏏", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- API DATA FETCHING ---
@st.cache_data(ttl=120) # Caches data for 2 mins to save your 100-request limit
def fetch_live_data():
    try:
        # Get live scores
        url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
        response = requests.get(url).json()
        return response.get('data', [])
    except Exception as e:
        st.error(f"Error connecting to API: {e}")
        return []

# --- POINT CALCULATION LOGIC ---
def get_player_points(player_name, match_data):
    """
    Simulated logic: In the Free API, ball-by-ball is limited. 
    This calculates points based on the score string provided in the API.
    """
    points = 0
    # Logic: If player appears in the 'status' or 'score' string, we assign base points.
    # Note: For high-accuracy individual stats, the 'Match Scorecard' API is needed.
    for match in match_data:
        if player_name in str(match.get('score', '')):
            points += 50 # Base points for playing well
        if "wickets" in str(match.get('status', '')).lower() and player_name in str(match.get('name')):
            points += 25
    return points

# --- APP UI ---
st.title("🏆 Family Cricket Fantasy League")
st.subheader("Real-time Scoreboard & Leaderboard")

live_matches = fetch_live_data()

# 1. LIVE MATCH SECTION
st.header("📺 Current Matches")
if live_matches:
    cols = st.columns(len(live_matches[:3])) # Show top 3 matches
    for i, match in enumerate(live_matches[:3]):
        with cols[i]:
            score_val = match['score'][0]['r'] if match.get('score') else "N/A"
            st.metric(label=match['name'], value=f"Score: {score_val}", delta=match['status'])
else:
    st.info("No live matches at the moment. Check back during game time!")

st.divider()

# 2. LEADERBOARD CALCULATION
st.header("🥇 Family Standings")
leaderboard_data = []
all_player_scores = {}

for member, players in FAMILY_TEAMS.items():
    total_score = 0
    for p in players:
        p_score = get_player_points(p, live_matches)
        total_score += p_score
        all_player_scores[p] = all_player_scores.get(p, 0) + p_score
    
    leaderboard_data.append({"Family Member": member, "Total Points": total_score})

# Display Leaderboard
df = pd.DataFrame(leaderboard_data).sort_values(by="Total Points", ascending=False)
st.dataframe(df, use_container_width=True, hide_index=True)

# 3. HIGHEST SCORE OF THE DAY
st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🌟 Player of the Day")
    if all_player_scores:
        top_player = max(all_player_scores, key=all_player_scores.get)
        st.success(f"**{top_player}** is leading with {all_player_scores[top_player]} points!")
    else:
        st.write("Match just started. No top players yet.")

with col_right:
    st.subheader("📈 My Team Progress")
    selected_member = st.selectbox("Select your name to see your squad performance:", list(FAMILY_TEAMS.keys()))
    squad = FAMILY_TEAMS[selected_member]
    st.write(f"Your Players: {', '.join(squad)}")

st.sidebar.write(f"**API Quota:** Your key has 100 hits/day. Use the refresh sparingly!")
if st.sidebar.button("Force Refresh Score"):
    st.cache_data.clear()
    st.rerun()
