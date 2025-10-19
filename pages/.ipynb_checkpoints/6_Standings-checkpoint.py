import streamlit as st
import pandas as pd
import db_utils

st.title("Weekly Fantasy Points & Standings")

standings = db_utils.load_teams()

st.dataframe(standings[['Place', 'team_name', 'manager', 'W', 'L', 'PF', 'PA']], hide_index = True, height = 450)
