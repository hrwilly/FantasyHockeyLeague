import streamlit as st
import pandas as pd
import db_utils
from streamlit_autorefresh import st_autorefresh

st.title("Add / Drop Players")

# --- Auto-refresh every 5 seconds ---
st_autorefresh(interval=5000, key="players_autorefresh")

# --- Load data ---
teams = db_utils.load_teams()
players = db_utils.load_players()
points = db_utils.load_points()
stats = db_utils.load_last_week_stats()
players = pd.merge(players, stats, on = ['Name', 'team'], how = 'left')
total = points.pivot_table(columns = 'Week', index = ['Name', 'team'], values = 'FantasyPoints', aggfunc = 'mean')
players = pd.merge(players, total.reset_index(), on = ['Name', 'team'], how = 'left')

if teams.empty:
    st.warning("No teams registered yet.")
    st.stop()

# --- Select your team ---
my_team_name = st.selectbox("Select your team:", teams["team_name"])

# --- Roster template for validation ---
roster_template = {"F": 6, "D": 4, "G": 2}
num_bench = 5

def build_roster_display(team_name):
    """Builds the current roster table with starters and bench labeled"""
    team_players = players[players["held_by"] == team_name]
    roster_display = []

    # Starting players
    for pos, slots in roster_template.items():
        starters = team_players[team_players["Pos."] == pos].head(slots)
        for _, row in starters.iterrows():
            roster_display.append(row)

    # Bench players
    for pos in roster_template.keys():
        extra = team_players[team_players["Pos."] == pos].iloc[roster_template[pos]:]
        for _, row in extra.iterrows():
            bench_row = row.copy()
            bench_row["Pos."] = f"Bench - {row['Pos.']}"
            roster_display.append(bench_row)

    display_df = pd.DataFrame(roster_display)
    if not display_df.empty:
        display_df = display_df[["Pos.", "Name", "team", "Ht.", "Wt."]]
    return display_df

# --- Display current roster ---
st.subheader(f"{my_team_name}'s Current Roster")
display_df = build_roster_display(my_team_name)
st.table(display_df)

# --- Free agents ---
def get_free_agents():
    return players[players["held_by"].isna()]

st.subheader("Available Free Agents")
free_agents = get_free_agents()
st.dataframe(free_agents.set_index(['Name', 'team', 'Pos.']).drop(['held_by'], axis = 1),
             height=500, use_container_width=True, width = 'stretch')

# --- Initialize session state for selections ---
if "add_player" not in st.session_state:
    st.session_state.add_player = ""
if "drop_player" not in st.session_state:
    st.session_state.drop_player = ""

# --- Function to build display strings ---
def format_options(df):
    df = df.copy()
    df["display"] = df["Name"] + " - " + df["Pos."] + " - " + df["team"]
    return df

# --- Add Player dropdown ---
add_df = format_options(free_agents)
add_options = [""] + add_df["display"].tolist()
add_index = add_options.index(st.session_state.add_player) if st.session_state.add_player in add_options else 0
selected_add_display = st.selectbox("Select a player to add:", add_options, index=add_index)
st.session_state.add_player = selected_add_display

# --- Drop Player dropdown ---
team_players = players[players["held_by"] == my_team_name]
drop_df = format_options(team_players)
drop_options = [""] + drop_df["display"].tolist()
drop_index = drop_options.index(st.session_state.drop_player) if st.session_state.drop_player in drop_options else 0
selected_drop_display = st.selectbox("Select a player to drop from your roster:", drop_options, index=drop_index)
st.session_state.drop_player = selected_drop_display

# --- Add & Drop button ---
if st.button("Add & Drop Player"):
    if not st.session_state.add_player or not st.session_state.drop_player:
        st.warning("Please select both a player to add and a player to drop.")
    else:
        # Map display string back to Name
        add_name = st.session_state.add_player.split(" - ")[0]
        drop_name = st.session_state.drop_player.split(" - ")[0]

        # Get positions
        pos_add = players.loc[players["Name"] == add_name, "Pos."].values[0]
        pos_drop = players.loc[players["Name"] == drop_name, "Pos."].values[0]

        # Count current players at that position
        current_count = len(players[(players["held_by"] == my_team_name) & (players["Pos."] == pos_add)])
        if pos_add == pos_drop:
            current_count -= 1

        # Bench-aware roster limit
        max_allowed = roster_template.get(pos_add, 0) + num_bench

        if current_count >= max_allowed:
            st.warning(f"No available {pos_add} slots (including bench). Choose a different player to drop.")
        else:
            # Perform add/drop
            players.loc[players["Name"] == add_name, "held_by"] = my_team_name
            players.loc[players["Name"] == drop_name, "held_by"] = None
            db_utils.save_players(players)
            st.success(f"Added {add_name} and dropped {drop_name}")

            # Clear selections
            st.session_state.add_player = ""
            st.session_state.drop_player = ""

            # --- Dynamic update ---
            display_df = build_roster_display(my_team_name)
            st.table(display_df)
            free_agents = get_free_agents()
            st.dataframe(free_agents.set_index(['Name', 'team', 'Pos.']).drop(['held_by'], axis = 1),
                         height=500, use_container_width=True, width = 'stretch')
