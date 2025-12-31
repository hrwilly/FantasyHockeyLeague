import streamlit as st
import pandas as pd
import numpy as np
import db_utils
from streamlit_autorefresh import st_autorefresh

st.title("🏒 Add / Drop Players")

# --- Auto-refresh ---
st_autorefresh(interval=100000, key="players_autorefresh")

# --- Load data ---
teams = db_utils.load_teams()
players = db_utils.load_players()

if teams.empty:
    st.warning("No teams registered yet.")
    st.stop()

# --- Select team ---
my_team_name = st.selectbox("Select your team:", teams["team_name"])

# --- Load lineup state ---
lineup_state = db_utils.load_lineup_state(my_team_name)

# --- Merge lineup state into players ---
players = players.merge(
    lineup_state[["player_name", "player_pos"]],
    left_on="Name",
    right_on="player_name",
    how="left"
)

players["player_pos"] = players["player_pos"].fillna("bench")

# --- Roster limits ---
roster_template = {"F": 6, "D": 4, "G": 2}
num_bench = 5

# --- Build roster display ---
def build_roster_display(team_name):
    team_players = players[players["held_by"] == team_name].copy()
    roster_rows = []

    # Starters
    for pos, slots in roster_template.items():
        starters = team_players[
            (team_players["Pos."] == pos) &
            (team_players["player_pos"] == "starter")
        ].head(slots)

        for _, row in starters.iterrows():
            roster_rows.append(row)

    # Bench
    bench_players = team_players[team_players["player_pos"] == "bench"]
    for _, row in bench_players.iterrows():
        bench_row = row.copy()
        bench_row["Pos."] = f"Bench - {row['Pos.']}"
        roster_rows.append(bench_row)

    return pd.DataFrame(roster_rows)

# --- Display roster ---
st.subheader(f"{my_team_name}'s Current Roster")
roster_df = build_roster_display(my_team_name)

if roster_df.empty:
    st.info("No players on roster yet.")
else:
    st.dataframe(
        roster_df.set_index(["Name", "team", "Pos."])
        .drop(columns=["held_by", "player_name", "player_pos"], errors="ignore"),
        height=500,
        use_container_width=True
    )

# --- Free agents ---
st.subheader("Available Free Agents")
free_agents = players[players["held_by"].isna()]

st.dataframe(
    free_agents.set_index(["Name", "team", "Pos."])
    .drop(columns=["held_by", "player_name", "player_pos"], errors="ignore"),
    height=500,
    use_container_width=True
)

# --- Session state ---
if "add_player" not in st.session_state:
    st.session_state.add_player = ""
if "drop_player" not in st.session_state:
    st.session_state.drop_player = ""

# --- Display helpers ---
def format_options(df):
    df = df.copy()
    df["display"] = df["Name"] + " - " + df["Pos."] + " - " + df["team"]
    return df

# --- Add dropdown ---
add_df = format_options(free_agents)
add_options = [""] + add_df["display"].tolist()
st.session_state.add_player = st.selectbox(
    "Select a player to add:",
    add_options,
    index=add_options.index(st.session_state.add_player)
    if st.session_state.add_player in add_options else 0
)

# --- Drop dropdown ---
team_players = players[players["held_by"] == my_team_name]
drop_df = format_options(team_players)
drop_options = [""] + drop_df["display"].tolist()
st.session_state.drop_player = st.selectbox(
    "Select a player to drop:",
    drop_options,
    index=drop_options.index(st.session_state.drop_player)
    if st.session_state.drop_player in drop_options else 0
)

# --- Add / Drop ---
if st.button("Add & Drop Player"):

    if not st.session_state.add_player or not st.session_state.drop_player:
        st.warning("Please select both a player to add and a player to drop.")
        st.stop()

    add_name = st.session_state.add_player.split(" - ")[0]
    drop_name = st.session_state.drop_player.split(" - ")[0]

    add_row = players.loc[players["Name"] == add_name].iloc[0]
    drop_row = players.loc[players["Name"] == drop_name].iloc[0]

    pos_add = add_row["Pos."]
    pos_drop = drop_row["Pos."]

    # --- Position limits (bench-aware) ---
    current_count = len(
        players[
            (players["held_by"] == my_team_name) &
            (players["Pos."] == pos_add)
        ]
    )

    if pos_add == pos_drop:
        current_count -= 1

    max_allowed = roster_template.get(pos_add, 0) + num_bench

    if current_count >= max_allowed:
        st.warning(f"No available {pos_add} slots (including bench).")
        st.stop()

    # --- Execute add/drop ---
    db_utils.add_drop_player(
        team_name=my_team_name,
        add_player=add_name,
        drop_player=drop_name,
        add_player_pos=pos_add,
        add_player_team=add_row["team"],
        starter=False
    )

    st.success(f"✅ Added {add_name} and dropped {drop_name}")

    # --- Reset selections ---
    st.session_state.add_player = ""
    st.session_state.drop_player = ""

