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
        'GP' : 0, 'G': 2, 'A': 1, 'Shots': 0.1, 'PIM': -0.5, 'GWG': 1,
        'PPG': 0.5, 'SHG': 0.5, '+/-': 0.5, 'FOW': 0.1,
        'FOL': -0.1, 'BLK': 0.5, 'W': 4, 'GA': -2,
        'SV': 0.2, 'SO': 3
    }
    for col, mult in multipliers.items():
        if col in scored.columns:
            scored[col] = scored[col] * mult

    scored['FantasyPoints'] = round(scored.sum(axis=1), 1)
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
    last_week = last_week.set_index(["Name", "team"])
    weekly_stats = (current_cum - last_week).fillna(0.0)

    weekly_scored = compute_fantasy_points(weekly_stats)

    # Save to session state so we can use after rerun
    st.session_state['weekly_scored'] = weekly_scored
    st.session_state['current_cum'] = current_cum

    st.success(f"✅ Weekly scoring calculated for {date.today().strftime('%Y-%m-%d')}")
    st.dataframe(weekly_scored.head(50))
    st.dataframe(current_cum.head(10))

# --- Save Weekly Scoring ---
if 'weekly_scored' in st.session_state and st.button('💾 Save Scoring'):
    st.markdown('Saving points...')

    points = st.session_state['weekly_scored']
    points = points.reset_index()
    points = points[['Name', 'team', 'FantasyPoints']]

    current_cum = st.session_state['current_cum']

    #db_utils.save_weekly_points(points)
    db_utils.save_last_week_stats(current_cum)
    st.success(f"✅ Weekly scoring saved for {date.today().strftime('%Y-%m-%d')}")

