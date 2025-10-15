import streamlit as st
import db_utils

st.title("📅 Matchups")

# --- Load matchups ---
matchups_df = db_utils.load_matchups()
managers = db_utils.load_teams()

matchups_df = (
        matchups_df
        .merge(managers.rename(columns={"team_name": "home_team", "manager": "manager_1"}), on="home_team")
        .merge(managers.rename(columns={"team_name": "away_team", "manager": "manager_2"}), on="away_team")
    )


selected_week = st.selectbox("Select week", sorted(matchups_df["week"].unique()))
week_matchups = matchups_df[matchups_df["week"] == selected_week]

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

st.write(f"### {selected_matchup['home_team']} vs {selected_matchup['away_team']}")
st.write(f"##### {selected_matchup['manager_1']} vs {selected_matchup['manager_2']}")
st.write(f"**Scores:** {selected_matchup['home_team_points']} - {selected_matchup['away_team_points']}")