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

num_teams = len(teams)
drafted_players = players[players["drafted_by"].notna()]
total_picks = len(drafted_players)

# --- Snake draft order for display only ---
def get_snake_order(round_num, team_list):
    return team_list if round_num % 2 == 1 else list(reversed(team_list))

num_rounds = 17
total_allowed_picks = num_rounds * num_teams
if total_picks >= total_allowed_picks:
    st.info("Draft is complete! No more picks.")
    st.stop()

current_round = total_picks // num_teams + 1
current_pick_index = total_picks % num_teams
current_round_order = get_snake_order(current_round, teams["team_name"].tolist())

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
if "team_name" not in st.session_state:
    st.session_state.team_name = st.selectbox("Select your team:", teams["team_name"])
selected_team = st.session_state.team_name

# --- Available players ---
available_players = players[players["drafted_by"].isna()].copy()
available_players = available_players.sort_values(
    by="Draft Round",
    key=lambda col: pd.to_numeric(col, errors="coerce"),
    na_position="last"
)

# --- Roster & bench limits ---
roster_template = {"F": 6, "D": 4, "G": 2}
num_bench = 5

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
    if pos in roster_template and starting_counts[pos] < roster_template[pos]:
        return True
    elif bench_count < num_bench:
        return True
    else:
        return False

available_players_team = available_players[available_players.apply(can_draft_player, axis=1)]


# --- Available Players Table ---
st.subheader("Available Players")
if available_players.empty:
    st.warning("No available players left!")
else:
    display_df = available_players.drop(columns=["drafted_by"])
    st.dataframe(display_df, width='stretch')

# --- Draft Controls ---
st.subheader("Draft Controls")
if not available_players_team.empty:
    available_players_team = available_players_team.copy()
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
        # Assign player to team
        players.loc[players["Name"] == chosen_player, "drafted_by"] = selected_team
    
        # Save to Supabase
        db_utils.save_player(players.loc[players["Name"] == chosen_player].iloc[0])
    
        # Refetch all players so roster updates immediately
        players = db_utils.load_players()
        my_team_players = players[players["drafted_by"] == selected_team]
    
        st.success(f"{selected_team} drafted {chosen_player}!")
else:
    st.info("Roster is full. You cannot draft more players.")

# --- My Roster Table ---
st.subheader("My Roster")
roster_rows = []

# Starting slots
for pos, slots in roster_template.items():
    for _ in range(slots):
        roster_rows.append({"Pos.": pos, "Name": "---", "team": "---", "Yr." : "---", "Ht.": "---", "Wt.": "---"})
# Bench slots
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
        for i in range(len(my_roster)):
            if my_roster.loc[i, "Pos."].startswith("Bench") and my_roster.loc[i, "Name"] == "---":
                my_roster.loc[i, "Pos."] = f"Bench - {pos}"
                my_roster.loc[i, ["Name", "team", "Yr.", "Ht.", "Wt."]] = row[["Name", "team", "Yr.", "Ht.", "Wt."]]
                break

st.table(my_roster)

# --- Draft Board ---
st.subheader("Draft Board")
draft_board = players[players["drafted_by"].notna()]
if not draft_board.empty:
    st.dataframe(draft_board[["Name", "Pos.", "team", "drafted_by"]], width='stretch')
else:
    st.info("No picks have been made yet.")
