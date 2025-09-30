import streamlit as st
import pandas as pd
import db_utils

st.title("🏒 Fantasy Draft Room")

# --- Load teams ---
teams = db_utils.load_teams()
if teams.empty:
    st.warning("No teams registered yet. Go to the Register page first.")
    st.stop()

num_teams = len(teams)

# --- Select your team ---
if "team_name" not in st.session_state:
    st.session_state["team_name"] = teams["team_name"].iloc[0]
selected_team = st.selectbox("Select your team:", teams["team_name"], index=teams["team_name"].tolist().index(st.session_state["team_name"]))
st.session_state["team_name"] = selected_team

# --- Snake draft order ---
def get_snake_order(round_num, team_list):
    return team_list if round_num % 2 == 1 else list(reversed(team_list))

# --- Load latest players from DB ---
def load_players_state():
    players_db = db_utils.load_players()
    drafted_players = players_db[players_db["drafted_by"].notna()]
    current_pick_number = len(drafted_players) + 1
    current_round = (current_pick_number - 1) // num_teams + 1
    current_pick_index = (current_pick_number - 1) % num_teams
    current_round_order = get_snake_order(current_round, teams["team_name"].tolist())
    current_team = current_round_order[current_pick_index]
    return players_db, drafted_players, current_pick_number, current_round, current_pick_index, current_round_order, current_team

players_db, drafted_players, current_pick_number, current_round, current_pick_index, current_round_order, current_team = load_players_state()

# --- Draft board ---
st.subheader("Draft Board")
if not drafted_players.empty:
    draft_board = drafted_players.sort_values("Pick_Number")
    st.dataframe(draft_board[["Pick_Number", "Name", "Pos.", "team", "drafted_by"]], width='stretch')
else:
    st.info("No players have been drafted yet.")

# --- Upcoming Draft Order ---
st.subheader("Upcoming Draft Order")
num_upcoming = 5
upcoming_picks = []
for i in range(num_upcoming):
    next_pick_index = (current_pick_index + i) % num_teams
    next_round = current_round + ((current_pick_index + i) // num_teams)
    next_order = get_snake_order(next_round, teams["team_name"].tolist())
    upcoming_picks.append((next_round, next_order[next_pick_index]))

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

# --- Available players ---
available_players = players_db[players_db["drafted_by"].isna()].copy()
available_players = available_players.sort_values(
    by="Draft Round", key=lambda col: pd.to_numeric(col, errors="coerce"), na_position="last"
)

st.subheader("Available Players")
if available_players.empty:
    st.warning("No available players left!")
else:
    st.dataframe(available_players.drop(columns=["drafted_by"]), width='stretch')

# --- Roster and bench limits ---
roster_template = {"F": 6, "D": 4, "G": 2}
num_bench = 5
my_team_players = players_db[players_db["drafted_by"] == selected_team]

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
if available_players_team.empty:
    st.info("No eligible players to draft for your roster.")
else:
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
        # Reload latest players
        players_db, drafted_players, current_pick_number, current_round, current_pick_index, current_round_order, current_team = load_players_state()

        # Check if player is still available
        if players_db.loc[players_db["Name"] == chosen_player, "drafted_by"].isna().all():
            # Draft player
            idx = players_db["Name"] == chosen_player
            players_db.loc[idx, "Pick_Number"] = current_pick_number
            players_db.loc[idx, "drafted_by"] = selected_team

            # Save to DB
            db_utils.save_player(players_db.loc[idx].iloc[0])

            # Reload full players list to update all UI elements
            players_db, drafted_players, current_pick_number, current_round, current_pick_index, current_round_order, current_team = load_players_state()

            # Update local session state for roster rendering
            st.session_state.players = players_db.copy()
            st.success(f"{selected_team} drafted {chosen_player}!")
        else:
            st.warning(f"{chosen_player} has already been drafted!")

# --- My Roster with Bench ---
st.subheader("My Roster")
my_team_players = players_db[players_db["drafted_by"] == selected_team]

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
