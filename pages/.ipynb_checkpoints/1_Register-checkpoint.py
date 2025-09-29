import streamlit as st
import db_utils

st.title("📋 Register Your Team")

team_name = st.text_input("Team Name")
manager = st.text_input("Manager Name")

if st.button("Register"):
    if not team_name or not manager:
        st.error("Please fill in both the team name and manager name.")
    else:
        # Check if the team already exists
        existing_team = db_utils.get_team_by_name(team_name)
        if existing_team is not None:
            st.error("That team name is already taken.")
        else:
            db_utils.add_team(team_name, manager)
            st.success(f"✅ Team **{team_name}** registered successfully!")

