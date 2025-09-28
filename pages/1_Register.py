import streamlit as st
import db_utils
import pandas as pd

st.title("📋 Register Your Team")

team_name = st.text_input("Team Name")
manager = st.text_input("Manager Name")

if st.button("Register"):
    teams = db_utils.load_teams()
    if team_name in teams["team_name"].values:
        st.error("That team name is already taken.")
    else:
        new_row = pd.DataFrame([{"team_name": team_name, "manager": manager}])
        teams = pd.concat([teams, new_row], ignore_index=True)
        db_utils.save_teams(teams)
        st.success(f"Team {team_name} registered!")
