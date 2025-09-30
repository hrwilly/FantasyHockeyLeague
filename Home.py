import streamlit as st
import db_utils

st.title("🏒 Fantasy College Hockey League")

st.write("Welcome to the league!")
st.write("Use the sidebar to navigate between pages.")

st.subheader("Scoring Breakdown:")
st.write("Goals: 2 pts each")
st.write("Assists: 1 pt each")
st.write("Shots: 0.1 pts each")
st.write("Penalty minutes: -0.5 pts each")
st.write("Game Winning Goals: 1 pt each")
st.write("Power Play Goals: 0.5 pts each")
st.write("Short Handed Goals: 0.5 pts each")
st.write("+/-: 0.5 pts each")
st.write("Faceoffs Won: 0.1 pts each")
st.write("Faceoffs Lost: -0.1 pts each")
st.write("Blocked Shots: 0.5 pts each")
st.write("Wins (for goalies): 4 pts each")
st.write("Goals Against: -2 pts each")
st.write("Saves: 0.2 pts each")
st.write("Shutouts: 3 pts each")

st.subheader("Rules:")

st.write('3 week of playoffs. Top 6 make it. Championship weekend 2/28. Playoffs start 2/14. Weeks off: 1/3, 12/27, 12/20, 12/13, 11/29.')
