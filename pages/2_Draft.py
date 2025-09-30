import streamlit as st
import pandas as pd
import db_utils
from streamlit_autorefresh import st_autorefresh

st.title("🏒 Fantasy Draft Room")

# --- Auto-refresh every 5 seconds ---
st_autorefresh(interval=5000, key="draft_autorefresh")

# --- Load teams and players ---
teams = db_utils.load_teams()
players = db_utils.load_players_safe()

if teams.empty:
    st.warning("No teams registered yet. Go to the Register page first.")
    st.stop()

# --- Ensure pick counter persists and resumes from saved state ---
if "pick_number" not in st.session_state:
    if "Pick_Number" in players.columns and players["Pick_Number"].dropna().size > 0:
        st.session_state.pick_number = int(players["Pick_Number"].dropna().max()) + 1
    else:
        st.session_state.pick_number = 1

# --- Snake draft order ---
num_teams = len(teams)
drafted_players = players[players["drafted_by"].notna()]
total_picks = len(drafted_players)

def get_snake_order(round_num, team_list):
    return team_list if round_num % 2 == 1 else list(reversed(team_list))

current_round = total_picks // num_teams + 1
current_round_order = get_snake_order(current_round, teams["team_name"].tolist())
current_pick_index = total_picks % num_teams
current_team = current_round_order[current_pick_index]

num_rounds = 17
total_allowed_picks = num_rounds * num_teams
if total_picks >= total_allowed_picks:
    st.info("Draft is complete! No more picks.")
    st.stop()

# --- Upcoming Draft Order ---
st.subheader("Upcoming Draft Order")
num_upcoming = 5
upcoming_picks = []
for i in range(num_upcoming):
    next_pick_index = (current_pick_index + i) % num_teams
    next_round = current_round + ((current_pick_index + i) // num_teams)
    next_order = get_snake_order(next_round, teams["team_name"].tolist())
    upcoming_team = next_order[next_pick_index]
    upcoming_picks.append((next_round, upcoming_team))

cols = st.columns(num_upcoming)
for col, (rnd, team) in zip(cols, upcoming_picks):
    short_name = team[:5]
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
            {short_name}<br>R{rnd}
        </div>
        """,
        unsafe_allow_html=True
    )

# --- Select your team ---
st.session_state["team_name"] = st.selectbox("Select your team:", teams["team_name"])
selected_team = st.session_state["team_name"]

# --- Available players ---
available_players = players[players["drafted_by"].isna()].copy()
available_players = available_players.sort_values(
    by="Draft Round", key=lambda col: pd.to_numeric(col, errors="coerce"), na_position="last"
)

st.subheader("Available Players")
if available_players.empty:
    st.warning("No available players left!")
else:
    display_df = available_players.drop(columns=["drafted_by"])
    st.dataframe(display_df, width='stretch')

# --- Roster and bench limits ---
roster_template = {"F": 6, "D": 4, "G": 2}
num_bench = 5

# --- My team players (always compute fresh from database) ---
my_team_players = players[players["drafted_by"] == selected_team]

starting_counts = {pos: 0 for pos in roster_template.keys()}
bench_count = 0
for _, row in my_team_players.iterrows():
    pos = row["Pos."]
    if pos in roster_template and starting_counts[pos] < roster_template[pos]:
        starting_counts[pos] += 1
    else:
        bench_count += 1

def can_draft_player(player_row):
    pos = player_row["Pos."]
    starting_limit = roster_template.get(pos, 0)
    if pos in roster_template and starting_counts[pos] < starting_limit:
        return True
    elif bench_count < num_bench:
        return True
    return False

available_players_team = available_players[available_players.apply(can_draft_player, axis=1)]

# --- Draft Controls ---
st.subheader("Draft Controls")
if not available_players_team.empty:
    available_players_team["label"] = available_players_team.apply(
        lambda row: f"{row['Name']} — {row['Pos.']} — {row['team']}", axis=1
    )
    label_to_name = dict(zip(available_players_team["label"], available_players_team["Name"]))

    selected_label = st.selectbox(
        "Select a player to draft:",
        options=available_players_team["label"].tolist(),
        key="player_select_dropdown"
    )
    chosen_player = label_to_name[selected_label]

    if st.button("Draft Player", key="draft_player_button"):
        # Update local dataframe
        idx = players["Name"] == chosen_player
        players.loc[idx, "Pick_Number"] = st.session_state.pick_number
        players.loc[idx, "drafted_by"] = selected_team
        st.session_state.pick_number += 1

        # Upsert to database
        db_utils.save_player(players.loc[idx].iloc[0])
        st.success(f"{selected_team} drafted {chosen_player}!")

        # Re-load players to refresh roster and draft board across devices
        players = db_utils.load_players_safe()
        my_team_players = players[players["drafted_by"] == selected_team]
        drafted_players = players[players["drafted_by"].notna()]

# --- My Roster with Bench ---
st.subheader("My Roster")
roster_rows = []
for pos, slots in roster_template.items():
    for _ in range(slots):
        roster_rows.append({"Pos.": pos, "Name": "---", "team": "---", "Yr.": "---", "Ht.": "---", "Wt.": "---"})
for _ in range(num_bench):
    roster_rows.append({"Pos.": "Bench", "Name": "---", "team": "---", "Yr.": "---", "Ht.": "---", "Wt.": "---"})

my_roster = pd.DataFrame(roster_rows)
pos_counts = {pos: 0 for pos in roster_template.keys()}

for _, row in my_team_players.iterrows():
    pos = row["Pos."]
    if pos in roster_template and pos_counts[pos] < roster_template[pos]:
        index = sum([roster_template[p] for p in roster_template
                     if list(roster_template.keys()).index(p) < list(roster_template.keys()).index(pos)]) + pos_counts[pos]
        my_roster.loc[index, ["Name", "team", "Yr.", "Ht.", "Wt."]] = row[["Name", "team", "Yr.", "Ht.", "Wt."]]
        pos_counts[pos] += 1
    else:
        for i in range(len(my_roster)):
            if my_roster.loc[i, "Pos."].startswith("Bench") and my_roster.loc[i, "Name"] == "---":
                my_roster.loc[i, "Pos."] = f"Bench - {pos}"
                my_roster.loc[i, ["Name", "team", "Yr.", "Ht.", "Wt."]] = row[["Name", "team", "Yr.", "Ht.", "Wt."]]
                break

st.table(my_roster)

# --- Draft Board ---
st.subheader("Draft Board")
draft_board = players[players["drafted_by"].notna()].copy()
if not draft_board.empty:
    draft_board = draft_board.sort_values("Pick_Number")
    st.dataframe(
        draft_board[["Pick_Number", "Name", "Pos.", "team", "drafted_by"]],
        width='stretch'
    )
else:
    st.info("No players have been drafted yet.")
