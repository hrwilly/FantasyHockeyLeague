import streamlit as st
import pandas as pd
from datetime import date
import db_utils

st.title("🏆 Commissioner Tools")

# --- Helper Functions ---
def get_team_names():
    url = r'https://collegehockeyinc.com/teams'
    college_teams = pd.read_html(url)[0]
    college_teams = college_teams['Name'].drop([0, 1, 5, 59]).dropna().reset_index(drop=True)
    return pd.DataFrame(college_teams)

def get_current_data(team):
    url = f'https://collegehockeyinc.com/teams/{team}/stats26-overall.php'
    offense = pd.read_html(url)[0]['Scoring']
    goalies = pd.read_html(url)[1]['Goaltending']

    offense = pd.read_html(url)[0]['Scoring']
    goalies = pd.read_html(url)[1]['Goaltending']
    
    offense = offense[offense['Name, Yr'] != 'TOTAL']
    goalies = goalies[goalies['Name, Yr'] != 'TOTALS']
    
    offense[['Name', 'Pos.', 'Yr']] = offense['Name, Yr'].str.split(',', expand=True)
    goalies[['Name', 'Yr']] = goalies['Name, Yr'].str.split(',', expand=True)
    
    points = pd.merge(offense, goalies, on = ['Name', 'Yr', 'GP'], how = 'outer')
    points = points.drop(['Name, Yr_x', 'Name, Yr_y'], axis = 1)
    points['team'] = team
    points = points.set_index(['Name', 'team'])

    stats_cols = ['GP', 'G','A','Shots','PIM','GWG','PPG','SHG','+/-','FOW','FOL','BLK','W','GA','SV','SO']
    points = points[stats_cols].fillna(0)

    return points

def compute_fantasy_points(data):
    scored = data.copy()
    multipliers = {
        'GP' : 0, 'G': 2, 'A': 1, 'Shots': 0.1, 'PIM': -0.3, 'GWG': 1,
        'PPG': 0.5, 'SHG': 1, '+/-': 0.5, 'FOW': 0.1,
        'FOL': -0.1, 'BLK': 0.5, 'W': 4, 'GA': -2,
        'SV': 0.2, 'SO': 3
    }
    for col, mult in multipliers.items():
        if col in scored.columns:
            scored[col] = scored[col] * mult

    scored['FantasyPoints'] = round(scored.sum(axis=1), 1)
    return scored

selected_week = st.selectbox("Select week", list(range(1, 16)))
st.session_state['selected_week'] = selected_week
selected_day = st.selectbox("Select day", list(range(1, 6)))
st.session_state['selected_day'] = selected_day

# --- Run Weekly Scoring ---
if st.button("🏁 Run Weekly Scoring"):
    st.markdown(f'Running scoring for week {st.session_state.selected_week}...')

    coll_teams = get_team_names()
    current_cum = pd.DataFrame()

    for team in coll_teams.Name:
        try:
            team_points = get_current_data(team[:-1])
            current_cum = pd.concat([current_cum, team_points])
        except Exception as e:
            st.warning(f"Skipping team {team[:-1]}: {e}")

    last_week = db_utils.load_last_week_stats()
    last_week = last_week.set_index(["Name", "team"])
    weekly_stats = (current_cum - last_week).fillna(0.0)

    weekly_scored = compute_fantasy_points(weekly_stats)

    # Save to session state so we can use after rerun
    st.session_state['weekly_scored'] = weekly_scored
    st.session_state['current_cum'] = current_cum

    st.success(f"✅ Weekly scoring calculated for Week {st.session_state.selected_week}")
    st.dataframe(weekly_scored.head(50))
    st.dataframe(current_cum.head(50))

# --- Save Weekly Scoring ---
if 'weekly_scored' in st.session_state and st.button('💾 Save Scoring'):
    st.markdown('Saving points...')

    points = st.session_state['weekly_scored']
    points = points.reset_index()
    points = points[['Name', 'team', 'FantasyPoints']]
    points = points[points['FantasyPoints'] != 0]

    current_cum = st.session_state['current_cum']

    db_utils.save_weekly_points(points, st.session_state.selected_week, st.session_state.selected_day)
    db_utils.save_last_week_stats(current_cum)
    st.success(f"✅ Weekly scoring saved for Week {st.session_state.selected_week}, Day {st.session_state.selected_day},")

if st.button('Run Matchups'):
    matchups_df = db_utils.load_matchups()
    managers = db_utils.load_teams()
    rosters_df = db_utils.load_roster()
    points = db_utils.load_points()
    
    matchups_df = (
            matchups_df
            .merge(managers.rename(columns={"team_name": "home_team", "manager": "manager_1"}), on="home_team")
            .merge(managers.rename(columns={"team_name": "away_team", "manager": "manager_2"}), on="away_team")
        )

    selected_week = st.session_state.selected_week
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

    db_utils.save_weekly_matchups(week_matchups)
    st.success(f"✅ Weekly matchup scores saved for Week {st.session_state.selected_week}")

    st.dataframe(week_matchups)