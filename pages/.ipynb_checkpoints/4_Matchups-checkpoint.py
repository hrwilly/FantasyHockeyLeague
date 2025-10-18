import streamlit as st
import db_utils

st.title("📅 Matchups")

# --- Load matchups ---
matchups_df = db_utils.load_matchups()
managers = db_utils.load_teams()
rosters_df = db_utils.load_roster()
points = db_utils.load_points()

matchups_df = (
        matchups_df
        .merge(managers.rename(columns={"team_name": "home_team", "manager": "manager_1"}), on="home_team")
        .merge(managers.rename(columns={"team_name": "away_team", "manager": "manager_2"}), on="away_team")
    )

selected_week = st.selectbox("Select week", sorted(matchups_df["week"].unique()))
week_matchups = matchups_df[matchups_df["week"] == selected_week]
week_rosters = rosters_df[rosters_df['week'] == selected_week]
week_points = points[points['Week'] == selected_week]

weekly = points[points['Week'] == selected_week][['Name', 'team', 'FantasyPoints', 'Week']]
weekly_total = weekly.pivot_table(columns='Week', index=['Name','team'], values='FantasyPoints', aggfunc='sum')
weekly_total['points'] = round(weekly_total.sum(axis=1), 1)
weekly_total = weekly_total.reset_index()[['Name', 'team', 'points']]

if len(week_points) != 0:
    week_rosters = week_rosters.merge(weekly_total.rename(columns = {'Name' : 'player_name'}), on = ['player_name', 'team'], how = 'left')
else:
    week_rosters['points'] = [0] * len(week_rosters)

# Initialize new columns
week_matchups["home_team_points"] = 0.0
week_matchups["away_team_points"] = 0.0

# Loop through each matchup and sum starter points
for idx, row in week_matchups.iterrows():
    home_team = row["home_team"]
    away_team = row["away_team"]

    home_points = (
        week_rosters
        .query("team_name == @home_team and player_pos == 'starter'")
        ["points"]
        .fillna(0)
        .sum()
    )

    away_points = (
        week_rosters
        .query("team_name == @away_team and player_pos == 'starter'")
        ["points"]
        .fillna(0)
        .sum()
    )

    week_matchups.loc[idx, "home_team_points"] = round(home_points, 1)
    week_matchups.loc[idx, "away_team_points"] = round(away_points, 1)

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
    st.dataframe(team1_starters[["player_name", "Pos.", 'team', 'points']], hide_index=True, height = 460)
    st.divider()
    st.caption("Bench")
    st.dataframe(team1_bench[["player_name", "Pos.", 'team', 'points']], hide_index=True)

with col2:
    st.markdown(f"### Lineup")
    st.caption("Starters")
    st.dataframe(team2_starters[["player_name", "Pos.", 'team', 'points']], hide_index=True, height = 460)
    st.divider()
    st.caption("Bench")
    st.dataframe(team2_bench[["player_name", "Pos.", 'team', 'points']], hide_index=True)