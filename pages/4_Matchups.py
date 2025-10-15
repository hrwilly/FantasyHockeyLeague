import streamlit as st
import db_utils

st.title("📅 Matchups")

# --- Load matchups ---
matchups_df = db_utils.load_matchups()
managers = db_utils.load_teams()
rosters_df = db_utils.load_roster()
points = db_utils.load_points()

st.dataframe(points.head(10))

matchups_df = (
        matchups_df
        .merge(managers.rename(columns={"team_name": "home_team", "manager": "manager_1"}), on="home_team")
        .merge(managers.rename(columns={"team_name": "away_team", "manager": "manager_2"}), on="away_team")
    )


selected_week = st.selectbox("Select week", sorted(matchups_df["week"].unique()))
week_matchups = matchups_df[matchups_df["week"] == selected_week]
week_rosters = rosters_df[rosters_df['week'] == selected_week]

st.dataframe(week_matchups.set_index('week').drop(['manager_1', 'manager_2'], axis = 1))

weeks = sorted(matchups_df["week"].unique())

# --- Create matchup labels like 'Team1 vs Team2' ---
week_matchups["matchup_label"] = week_matchups.apply(
    lambda row: f"{row['home_team']} vs {row['away_team']}", axis=1
)

# --- Dropdown to select matchup ---
selected_matchup_label = st.selectbox(
        "Select Matchup",
        week_matchups["matchup_label"]
)

# --- Get the selected matchup row ---
selected_matchup = week_matchups[
        week_matchups["matchup_label"] == selected_matchup_label
].iloc[0]



# --- Display matchup info ---
st.markdown(f"## {selected_matchup['home_team']} vs {selected_matchup['away_team']}")
col1, col2 = st.columns(2)

with col1:
    st.markdown(f"### {selected_matchup['home_team']}")
    st.caption(f"Manager: {selected_matchup['manager_1']}")
    st.metric(label="Score", value=selected_matchup['home_team_points'] or 0)

    with col2:
        st.markdown(f"### {selected_matchup['away_team']}")
        st.caption(f"Manager: {selected_matchup['manager_2']}")
        st.metric(label="Score", value=selected_matchup['away_team_points'] or 0)

st.divider()

# --- Show active rosters ---
# Filter to each team’s roster
team1_roster = week_rosters.query("team_name == @selected_matchup['home_team']")
team2_roster = week_rosters.query("team_name == @selected_matchup['away_team']")

# Separate starters and bench
team1_starters = team1_roster[team1_roster["player_pos"] == "starter"]
team1_bench = team1_roster[team1_roster["player_pos"] == "bench"]

team2_starters = team2_roster[team2_roster["player_pos"] == "starter"]
team2_bench = team2_roster[team2_roster["player_pos"] == "bench"]

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"### Lineup")
    st.caption("Starters")
    st.dataframe(team1_starters[["player_name", "player_pos"]], hide_index=True)
    st.divider()
    st.caption("Bench")
    st.dataframe(team1_bench[["player_name", "player_pos"]], hide_index=True)

with col2:
    st.markdown(f"### Lineup")
    st.caption("Starters")
    st.dataframe(team2_starters[["player_name", "player_pos"]], hide_index=True)
    st.divider()
    st.caption("Bench")
    st.dataframe(team2_bench[["player_name", "player_pos"]], hide_index=True)