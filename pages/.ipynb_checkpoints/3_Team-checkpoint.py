import streamlit as st
import pandas as pd
import db_utils
import time

st.title("My Team")

# --- Auto-refresh every 5 seconds ---
refresh_interval = 5
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()

if time.time() - st.session_state["last_refresh"] > refresh_interval:
    st.session_state["last_refresh"] = time.time()
    st.experimental_rerun()

# --- Load data ---
teams = db_utils.load_teams()
players = db_utils.load_players()

if teams.empty:
    st.warning("No teams registered yet.")
    st.stop()

# --- Select your team ---
selected_team = st.selectbox("Select your team:", teams["team_name"])

# --- Filter players for this team ---
my_team_players = players[players["drafted_by"] == selected_team].copy()

if my_team_players.empty:
    st.info("No players on your team yet.")
    st.stop()

# --- Roster template and bench ---
roster_template = {"F": 6, "D": 4, "G": 2}  # starting positions
num_bench = 5

# --- Build fixed-order roster with placeholders ---
roster_rows = []
for pos, slots in roster_template.items():
    for _ in range(slots):
        roster_rows.append({"Pos.": pos, "Name": "---", "team": "---", "Ht.": "---", "Wt.": "---"})
for _ in range(num_bench):
    roster_rows.append({"Pos.": "Bench", "Name": "---", "team": "---", "Ht.": "---", "Wt.": "---"})

my_roster = pd.DataFrame(roster_rows)

# --- Fill roster with drafted players ---
pos_counts = {pos: 0 for pos in roster_template.keys()}
bench_count = 0

for _, row in my_team_players.iterrows():
    pos = row["Pos."]
    if pos in roster_template and pos_counts[pos] < roster_template[pos]:
        index = sum([roster_template[p] for p in roster_template
                     if list(roster_template.keys()).index(p) < list(roster_template.keys()).index(pos)]) + pos_counts[pos]
        my_roster.loc[index, ["Name", "team", "Ht.", "Wt."]] = row[["Name", "team", "Ht.", "Wt."]]
        pos_counts[pos] += 1
    else:
        # Bench slots labeled "Bench - Pos"
        for i in range(len(my_roster)):
            if my_roster.loc[i, "Pos."].startswith("Bench") and my_roster.loc[i, "Name"] == "---":
                my_roster.loc[i, "Pos."] = f"Bench - {pos}"
                my_roster.loc[i, ["Name", "team", "Ht.", "Wt."]] = row[["Name", "team", "Ht.", "Wt."]]
                bench_count += 1
                break

# --- Display roster ---
st.subheader(f"{selected_team}'s Roster")
st.table(my_roster)

# --- Interactive Swap ---
st.subheader("Swap Players (Starters ↔ Bench)")

# Initialize session state
if "swap1" not in st.session_state:
    st.session_state.swap1 = ""
if "swap2" not in st.session_state:
    st.session_state.swap2 = ""

# Reload players to ensure latest
players = db_utils.load_players()
my_team_players = players[players["drafted_by"] == selected_team].copy()

# Build starter & bench lists from displayed roster
starters = my_roster[~my_roster["Pos."].str.startswith("Bench") & (my_roster["Name"] != "---")]
bench = my_roster[my_roster["Pos."].str.startswith("Bench") & (my_roster["Name"] != "---")]

# --- Starter selection ---
swap1_options = [""] + starters["Name"].tolist()
swap1_index = swap1_options.index(st.session_state.swap1) if st.session_state.swap1 in starters["Name"].tolist() else 0
st.session_state.swap1 = st.selectbox("Select Starter to swap out", swap1_options, index=swap1_index)

# --- Bench selection (filtered by position of starter) ---
if st.session_state.swap1:
    pos1 = my_roster.loc[my_roster["Name"] == st.session_state.swap1, "Pos."].values[0]
    swap2_list = bench[bench["Pos."].str.endswith(pos1)]["Name"].tolist()
else:
    swap2_list = []

swap2_options = [""] + swap2_list
swap2_index = swap2_options.index(st.session_state.swap2) if st.session_state.swap2 in swap2_list else 0
st.session_state.swap2 = st.selectbox("Select Bench player to swap in", swap2_options, index=swap2_index)

# --- Swap action ---
if st.button("Swap Players") and st.session_state.swap1 and st.session_state.swap2:
    idx1 = players.index[players["Name"] == st.session_state.swap1][0]
    idx2 = players.index[players["Name"] == st.session_state.swap2][0]

    # Swap rows completely to preserve all info
    players.loc[[idx1, idx2]] = players.loc[[idx2, idx1]].values
    db_utils.save_players(players)

    st.success(f"Swapped {st.session_state.swap1} and {st.session_state.swap2}")
    st.experimental_rerun()
