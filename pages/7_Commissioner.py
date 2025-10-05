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
    return college_teams

def get_current_data(team):
    url = f'https://collegehockeyinc.com/teams/{team}/stats26-overall.php'
    offense = pd.read_html(url)[0]['Scoring']
    goalies = pd.read_html(url)[1]['Goaltending']

    offense = offense[offense['Name, Yr'] != 'TOTAL'].set_index('Name, Yr')
    goalies = goalies[goalies['Name, Yr'] != 'TOTALS'].set_index('Name, Yr')

    points = pd.concat([offense, goalies], axis=1).reset_index()
    points[['Name', 'Pos.', 'Yr']] = points['Name, Yr'].str.split(',', expand=True)
    points.index = points['Name']

    stats_cols = ['G','A','Shots','PIM','GWG','PPG','SHG','+/-','FOW','FOL','BLK','W','GA','SV','SO']
    points = points[stats_cols].fillna(0)
    points['team'] = team
    return points

def compute_fantasy_points(data):
    scored = data.copy()
    multipliers = {
        'G': 2, 'A': 1, 'Shots': 0.1, 'PIM': -0.5, 'GWG': 1,
        'PPG': 0.5, 'SHG': 0.5, '+/-': 0.5, 'FOW': 0.1,
        'FOL': -0.1, 'BLK': 0.5, 'W': 4, 'GA': -2,
        'SV': 0.2, 'SO': 3
    }
    for col, mult in multipliers.items():
        if col in scored.columns:
            scored[col] = scored[col] * mult

    scored['FantasyPoints'] = scored.sum(axis=1)
    return scored

# --- Run Weekly Scoring ---
if st.button("🏁 Run Weekly Scoring"):
    st.markdown('Running scoring...')

    coll_teams = get_team_names()
    current_cum = pd.DataFrame()

    st.dataframe(coll_teams)

    for team in coll_teams.Name:
        try:
            team_points = get_current_data(team[:-1])
            current_cum = pd.concat([current_cum, team_points])
        except Exception as e:
            st.warning(f"Skipping team {team[:-1]}: {e}")

    last_week = db_utils.load_last_week_stats()
    last_week = last_week.set_index("Name")
    weekly_stats = (current_cum.drop('team', axis=1) - last_week.drop('team', axis=1)).fillna(0.0)

    weekly_scored = compute_fantasy_points(weekly_stats)

    # Save to session state so we can use after rerun
    st.session_state['weekly_scored'] = weekly_scored
    st.session_state['current_cum'] = current_cum

    st.success(f"✅ Weekly scoring updated for {date.today().strftime('%Y-%m-%d')}")
    st.dataframe(weekly_scored.head(50))

# --- Save Weekly Scoring ---
if 'weekly_scored' in st.session_state and st.button('💾 Save Scoring'):
    st.markdown('Saving points...')

    current_cum = st.session_state['current_cum']
    weekly_scored = st.session_state['weekly_scored']

    points = pd.merge(
        current_cum[['Name', 'team']],
        weekly_scored[['Name', 'FantasyPoints']],
        on='Name',
        how='outer'
    )

    st.write("👉 Debug: Points DataFrame", points)

    resp = db_utils.save_weekly_scoring(points)
    if resp and hasattr(resp, "data"):
        st.success(f"✅ Weekly scoring saved for {date.today().strftime('%Y-%m-%d')}")
    else:
        st.error("❌ Failed to save weekly scoring. Check logs.")
