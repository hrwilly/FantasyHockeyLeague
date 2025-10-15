import streamlit as st

st.title("📅 Matchups")

# --- Load matchups ---
matchups_df = db_utils.load_matchups()

selected_week = st.selectbox("Select week", sorted(matchups_df["week"].unique()))
week_matchups = matchups_df[matchups_df["week"] == selected_week]

st.dataframe(week_matchups)
