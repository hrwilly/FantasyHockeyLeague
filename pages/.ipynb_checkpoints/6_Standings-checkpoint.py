import streamlit as st
import pandas as pd
import db_utils

st.title("Weekly Fantasy Points & Standings")

standings = db_utils.load_teams()

st.dataframe(standings.sort_values(['W', 'PF'], hide_index = True)
