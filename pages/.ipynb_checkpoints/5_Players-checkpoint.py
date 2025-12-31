import streamlit as st
import pandas as pd
import numpy as np
import db_utils

st.title("🏒 Add / Drop Players")

# ======================================================
# CACHED LOADERS
# ======================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_teams_cached():
    return db_utils.load_teams()

@st.cache_data(ttl=180, show_spinner=False)
def load_players_cached():
    return db_utils.load_players()

@st.cache_data(ttl=180, show_spinner=False)
def load_last_week_stats_cached():
    return db_utils.load_last_week_stats()

@st.cache_data(ttl=30, show_spinner=False)
def load_lineup_state_team_cached(team_name: str):
    return db_utils.load_lineup_state(team_name)

with st.sidebar:
    if st.button("🔄 Refresh cached data"):
        st.cache_data.clear()
        st.rerun()

# ======================================================
# LOAD DATA
# ======================================================
teams = load_teams_cached()
players = load_players_cached()
stats = load_last_week_stats_cached()

if teams.empty:
    st.warning("No teams registered yet.")
    st.stop()

# Merge last_week_stats onto players so we can display all stat columns
if stats is not None and not stats.empty:
    players = players.merge(stats, on=["Name", "team"], how="left")

# ======================================================
# SELECT TEAM
# ======================================================
my_team_name = st.selectbox("Select your team:", teams["team_name"])

# Load lineup_state so we can show starter/bench status on roster
lineup_state = load_lineup_state_team_cached(my_team_name)

if lineup_state is not None and not lineup_state.empty:
    ls_small = lineup_state[["player_name", "player_pos"]].copy()
    players = players.merge(ls_small, left_on="Name", right_on="player_name", how="left")
else:
    players["player_pos"] = np.nan

players["player_pos"] = players["player_pos"].fillna("bench")

# ======================================================
# DISPLAY: TEAM ROSTER (WITH ALL STATS COLS)
# Remove held_by from display
# ======================================================
st.subheader(f"{my_team_name}'s Current Roster")

team_roster = players[players["held_by"] == my_team_name].copy()

front_cols = [c for c in ["Name", "Pos.", "team", "player_pos"] if c in team_roster.columns]
rest_cols = [
    c for c in team_roster.columns
    if c not in front_cols and c not in ["player_name", "held_by"]
]
roster_display_cols = front_cols + rest_cols

if team_roster.empty:
    st.info("No players on roster yet.")
else:
    st.dataframe(
        team_roster[roster_display_cols].set_index(["Name", "team", "Pos."]),
        use_container_width=True,
        height=480
    )

# ======================================================
# DISPLAY: FREE AGENTS (WITH ALL STATS COLS)
# Remove held_by + player_pos from display
# ======================================================
st.subheader("Available Free Agents")

free_agents = players[players["held_by"].isna()].copy()

fa_front = [c for c in ["Name", "Pos.", "team"] if c in free_agents.columns]
fa_rest = [
    c for c in free_agents.columns
    if c not in fa_front
    and c not in ["player_name", "held_by", "player_pos"]
]
fa_display_cols = fa_front + fa_rest

st.dataframe(
    free_agents[fa_display_cols].set_index(["Name", "team", "Pos."]),
    use_container_width=True,
    height=480
)

# ======================================================
# ADD/DROP UI
# ======================================================
st.divider()
st.subheader("Add & Drop")

if "add_player" not in st.session_state:
    st.session_state.add_player = ""
if "drop_player" not in st.session_state:
    st.session_state.drop_player = ""

def format_options(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["display"] = (
        out["Name"].astype(str) + " - "
        + out["Pos."].astype(str) + " - "
        + out["team"].astype(str)
    )
    return out

# Add selection
add_df = format_options(free_agents)
add_options = [""] + add_df["display"].tolist()
st.session_state.add_player = st.selectbox(
    "Select a player to add:",
    add_options,
    index=add_options.index(st.session_state.add_player)
    if st.session_state.add_player in add_options else 0
)

# Drop selection
drop_df = format_options(team_roster)
drop_options = [""] + drop_df["display"].tolist()
st.session_state.drop_player = st.selectbox(
    "Select a player to drop:",
    drop_options,
    index=drop_options.index(st.session_state.drop_player)
    if st.session_state.drop_player in drop_options else 0
)

# ======================================================
# EXECUTE ADD/DROP
# Default starter/bench of added player = whatever dropped player was
# ======================================================
if st.button("✅ Add & Drop Player"):
    if not st.session_state.add_player or not st.session_state.drop_player:
        st.warning("Please select both a player to add and a player to drop.")
        st.stop()

    add_name = st.session_state.add_player.split(" - ")[0].strip()
    drop_name = st.session_state.drop_player.split(" - ")[0].strip()

    # Grab the row for the player being added
    add_row = players.loc[players["Name"] == add_name].iloc[0]

    # Determine dropped player's current lineup position (starter/bench)
    # Prefer team_roster since it already has player_pos merged in
    dropped_pos = "bench"
    try:
        dropped_pos = (
            team_roster.loc[team_roster["Name"] == drop_name, "player_pos"]
            .iloc[0]
        )
        if pd.isna(dropped_pos) or dropped_pos not in ("starter", "bench"):
            dropped_pos = "bench"
    except Exception:
        dropped_pos = "bench"

    starter_flag = (dropped_pos == "starter")

    db_utils.add_drop_player(
        team_name=my_team_name,
        add_player=add_name,
        drop_player=drop_name,
        add_player_pos=add_row["Pos."],
        add_player_team=add_row["team"],
        starter=starter_flag,   # ✅ matches dropped player's slot
    )

    st.success(
        f"✅ Added {add_name} and dropped {drop_name} "
        f"({add_name} set to {'starter' if starter_flag else 'bench'})"
    )

    # Reset selections
    st.session_state.add_player = ""
    st.session_state.drop_player = ""

    # Clear cache so UI reflects changes immediately
    st.cache_data.clear()
    st.rerun()
