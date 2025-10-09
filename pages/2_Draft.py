import streamlit as st
import pandas as pd
import db_utils
from streamlit_autorefresh import st_autorefresh

st.title("🏒 Fantasy Draft Room")

# --- Auto-refresh every 5 seconds ---
st_autorefresh(interval=5000, key="draft_autorefresh")

# --- Load teams ---
if "teams" not in st.session_state:
    st.session_state.teams = db_utils.load_teams()
teams = st.session_state.teams
if teams.empty:
    st.warning("No teams registered yet. Go to the Register page first.")
    st.stop()

# --- Load draft board from Supabase ---
def load_draft_board():
    df = db_utils.load_draft_board()  # implement this in db_utils
    return df.sort_values(by=["Round", "Pick"])

draft_board = load_draft_board()

# --- Current pick and upcoming picks ---
drafted = draft_board[draft_board["FantasyTeam"].notna()]
next_picks = draft_board[draft_board["FantasyTeam"].isna()].head(5)

st.subheader("Upcoming Draft Order")
cols = st.columns(len(next_picks))
for col, (_, row) in zip(cols, next_picks.iterrows()):
    short_name = row["team"][:10]
    col.markdown(
        f"""
        <div style="
            background-color:#4CAF50;
            color:white;
            padding:10px;
            text-align:center;
            border-radius:5px;
            font-weight:bold;
        ">
            {short_name}<br>R{row['Round']} P{row['Pick']}
        </div>
        """,
        unsafe_allow_html=True
    )

# --- Select your team ---
st.session_state["team_name"] = st.selectbox("Select your team:", teams["team_name"])
selected_team = st.session_state["team_name"]

# --- Available players ---
available_players = draft_board[draft_board["FantasyTeam"].isna()].copy()
available_players = available_players.sort_values(by=["Round", "Pick"])

st.subheader("Available Players")
if available_players.empty:
    st.warning("No available players left!")
else:
    st.dataframe(
        available_players[["Name", "Pos.", "team", "Round", "Pick"]],
        width='stretch'
    )

# --- Draft Controls ---
st.subheader("Draft Controls")

available_players["label"] = available_players.apply(
    lambda row: f"{row['Name']} — {row['Pos.']} — {row['team']}", axis=1
)
label_to_name = dict(zip(available_players["label"], available_players["Name"]))

selected_label = st.selectbox(
    "Select a player to draft:",
    options=available_players["label"].tolist(),
    key="player_select_dropdown"
)
chosen_player = label_to_name[selected_label]

if st.button("Draft Player", key="draft_player_button"):
    idx = draft_board["Name"] == chosen_player
    draft_board.loc[idx, "FantasyTeam"] = selected_team
    db_utils.update_draft_pick(chosen_player, selected_team)  # implement in db_utils
    st.success(f"{selected_team} drafted {chosen_player}!")
    # Refresh draft board
    draft_board = load_draft_board()

# --- Draft Board Display ---
st.subheader("Draft Board")
if not draft_board.empty:
    st.dataframe(
        draft_board[["Round", "Pick", "Name", "Pos.", "team", "FantasyTeam"]],
        width='stretch'
    )
else:
    st.info("No players have been drafted yet.")
