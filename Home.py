import streamlit as st
import db_utils

st.title("🏒 Fantasy College Hockey League")

st.write("Welcome to the league!")
st.write("Use the sidebar to navigate between pages.")

st.subheader("Scoring Breakdown:")

st.subheader("Rules:")

st.write('3 week of playoffs. Top 6 make it. Championship weekend 2/28. Playoffs start 2/14. Weeks off: 1/3, 12/27, 12/20, 12/13, 11/29.')

# Initialize data
db_utils.init_data()
