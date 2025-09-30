import streamlit as st
import pandas as pd
import db_utils
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("🏒 Fantasy Draft Room")

# --- Auto-refresh every 5 seconds ---
st_autorefresh(interval=5000, key="draft_autorefresh")

# --- Load teams and players ---
teams = db_utils.load_teams()
players = db_utils.load_players()

if teams.empty:
    st.warning("No teams registered yet. Go to the Register page first.")
    st.stop()

# --- Define roster limits ---
roster_template = {"F": 6, "D": 4, "G": 2}
num_bench = 5
max_total_players = sum(roster_template.values()) + num_bench

# --- Count drafted players for your team ---
if "team_name" not in st.session_state:
    st.session_state.team_name = st.selectbox("Select your team:", teams["team_name"])
selected_team = st.session_state.team_name

my_team_players = players[players["drafted_by"] == selected_team]

starting_counts = {pos: 0 for pos in roster_template.keys()}
bench_count = 0
for _, row in my_team_players.iterrows():
    pos = row["Pos."]
    if pos in roster_template and starting_counts[pos] < roster_template[pos]:
        starting_counts[pos] += 1
    else:
        bench_count += 1

# --- Function to check if a player can be drafted ---
def can_draft_player(player_row):
    pos = player_row["Pos."]
    if pos in roster_template and starting_counts[pos] < roster_template[pos]:
        return True  # space in starting slot
    elif bench_count < num_bench:
        return True  # space in bench
    else:
        return False

# --- Available players ---
available_players = players[players["drafted_by"].isna()].copy()
available_players = available_players.sort_values(
    by="Draft Round",
    key=lambda col: pd.to_numeric(col, errors="coerce"),
    na_position="last"
)

# --- Filter available players respecting roster limits ---
available_players_team = available_players[available_players.apply(can_draft_player, axis=1)]

# --- Draft Controls ---
st.subheader("Draft Controls")

if not available_players_team.empty:
    available_players_team = available_players_team.copy()
    available_players_team["label"] = available_players_team.apply(
        lambda row: f"{row['Name']} — {row['Pos.']} — {row['team']}", axis=1
    )
    label_to_name = dict(
        zip(available_players_team["label"], available_players_team["Name"])
    )

    selected_label = st.selectbox(
        "Select a player to draft:",
        options=available_players_team["label"].tolist(),
        key="player_select_dropdown"
    )
    chosen_player = label_to_name[selected_label]

    if st.button("Draft Player", key="draft_player_button"):
        # Assign player to team
        players.loc[players["Name"] == chosen_player, "drafted_by"] = selected_team

        # Save to Supabase
        db_utils.save_player(players.loc[players["Name"] == chosen_player].iloc[0])

        st.success(f"{selected_team} drafted {chosen_player}!")
        st.session_state.draft_triggered = True
else:
    st.info("Roster is full. You cannot draft more players.")

# --- Available Players Table ---
st.subheader("Available Players")
if available_players.empty:
    st.warning("No available players left!")
else:
    display_df = available_players.drop(columns=["drafted_by"])
    st.dataframe(display_df, width='stretch')

# --- My Roster Table ---
st.subheader("My Roster")
roster_rows = []

# Starting positions
for pos, slots in roster_template.items():
    for _ in range(slots):
        roster_rows.append({"Pos.": pos, "Name": "---", "team": "---", "Yr." : "---", "Ht.": "---", "Wt.": "---"})
# Bench positions
for _ in range(num_bench):
    roster_rows.append({"Pos.": "Bench", "Name": "---", "team": "---", "Yr." : "---", "Ht.": "---", "Wt.": "---"})

my_roster = pd.DataFrame(roster_rows)
pos_counts = {pos: 0 for pos in roster_template.keys()}

for _, row in my_team_players.iterrows():
    pos = row["Pos."]
    if pos in roster_template and pos_counts[pos] < roster_template[pos]:
        index = sum([roster_template[p] for p in roster_template if list(roster_template.keys()).index(p) < list(roster_template.keys()).index(pos)]) + pos_counts[pos]
        my_roster.loc[index, ["Name", "team", "Yr.", "Ht.", "Wt."]] = row[["Name", "team", "Yr.", "Ht.", "Wt."]]
        pos_counts[pos] += 1
    else:
        # Fill bench
        for i in range(len(my_roster)):
            if my_roster.loc[i, "Pos."].startswith("Bench") and my_roster.loc[i, "Name"] == "---":
                my_roster.loc[i, "Pos."] = f"Bench - {pos}"
                my_roster.loc[i, ["Name", "team", "Yr.", "Ht.", "Wt."]] = row[["Name", "team", "Yr.", "Ht.", "Wt."]]
                break

st.table(my_roster)

# --- Draft Board Table ---
st.subheader("Draft Board")
draft_board = players[players["drafted_by"].notna()]
if not draft_board.empty:
    draft_board = draft_board.sort_values("Pick_Number")
    st.dataframe(
        draft_board[["Pick_Number", "Name", "Pos.", "team", "drafted_by"]],
        width='stretch'
    )
else:
    st.info("No picks have been made yet.")
