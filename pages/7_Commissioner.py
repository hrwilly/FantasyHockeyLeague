# pages/Commissioner.py
import streamlit as st
import pandas as pd
from datetime import date
import db_utils

st.title("🏆 Commissioner Tools")

def get_team_names():
    url = r'https://collegehockeyinc.com/teams'
    college_teams = pd.read_html(url)[0]
    college_teams = college_teams['Name'].drop([0, 1, 5, 59]).dropna().reset_index().drop(['index'], axis = 1)

    return college_teams
    

def get_current_data(team):
    url = r'https://collegehockeyinc.com/teams/' + team + '/stats26-overall.php'
    offense = pd.read_html(url)[0]['Scoring']
    goalies = pd.read_html(url)[1]['Goaltending']

    offense = offense[offense['Name, Yr'] != 'TOTAL'].set_index('Name, Yr')
    goalies = goalies[goalies['Name, Yr'] != 'TOTALS'].set_index('Name, Yr')

    points = pd.concat([offense, goalies], axis = 1)
    points = points.reset_index()
    points[['Name', 'Pos.', 'Yr']] = points['Name, Yr'].str.split(',', expand = True)
    points.index = points['Name']

    points = points[['G','A','Shots','PIM','GWG','PPG','SHG','+/-','FOW','FOL','BLK','W','GA','SV','SO']].fillna(0)
    points['team'] = [team] * len(points)

    return points

# --- Define fantasy scoring function ---
def compute_fantasy_points(data):
    """
    Apply your scoring rules to a DataFrame with player stats.
    """
    scored = data.copy()

    for col, multiplier in {
        'G': 2,
        'A': 1,
        'Shots': 0.1,
        'PIM': -0.5,
        'GWG': 1,
        'PPG': 0.5,
        'SHG': 0.5,
        '+/-': 0.5,
        'FOW': 0.1,
        'FOL': -0.1,
        'BLK': 0.5,
        'W': 4,
        'GA': -2,
        'SV': 0.2,
        'SO': 3
    }.items():
        if col in scored.columns:
            scored[col] = scored[col] * multiplier

    # Sum total fantasy points
    scored['FantasyPoints'] = scored.sum(axis=1)
    return scored

# --- Run Weekly Scoring ---
if st.button("🏁 Run Weekly Scoring"):
    st.markdown('Running scoring...')

    coll_teams = get_team_names()
    current_cum = pd.DataFrame()

    for team in coll_teams.Name:
        try:
            team_points = get_current_data(team[:-1])
            current_cum = pd.concat([current_cum, team_points])
        except Exception as e:
            st.warning(f"Skipping team {team[:-1]}: {e}")

    last_week = db_utils.load_last_week_stats()

    last_week = last_week.set_index("Name")
    weekly_stats = current_cum.copy()
    weekly_stats = (weekly_stats.drop('team', axis = 1) - last_week.drop('team', axis = 1)).fillna(0.0)
    
    # Step 2: Compute fantasy points
    weekly_scored = compute_fantasy_points(weekly_stats)

    if st.button('Save Scoring'):
        # --- Save current cumulative stats as "last_week" for next run ---
        db_utils.save_last_week_stats(current_cum.reset_index())

        points = pd.merge(current_cum[['Name', 'team']], weekly_scored[['Name', 'FantasyPoints']], on = 'Name', how = 'outer')
        db_utils.save_weekly_scoring(points)
    
    st.success(f"✅ Weekly scoring updated for {date.today().strftime('%Y-%m-%d')}")
    st.dataframe(weekly_scored.head(50))