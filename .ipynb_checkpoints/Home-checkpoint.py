import streamlit as st
import db_utils

st.title("🏒 Fantasy College Hockey League")

st.write("Welcome to the league!")
st.write("Use the sidebar to navigate between pages.")

st.subheader("Scoring Breakdown:")

# List of stats and their points
scoring = [
    ("Goals", "2 pts each"),
    ("Assists", "1 pt each"),
    ("Shots", "0.1 pts each"),
    ("Penalty minutes", "-0.5 pts each"),
    ("Game Winning Goals", "1 pt each"),
    ("Power Play Goals", "0.5 pts each"),
    ("Short Handed Goals", "0.5 pts each"),
    ("+/-", "0.5 pts each"),
    ("Faceoffs Won", "0.1 pts each"),
    ("Faceoffs Lost", "-0.1 pts each"),
    ("Blocked Shots", "0.5 pts each"),
    ("Wins (for goalies)", "4 pts each"),
    ("Goals Against", "-2 pts each"),
    ("Saves", "0.2 pts each"),
    ("Shutouts", "3 pts each"),
]

# Loop through and display in two columns
for stat, points in scoring:
    col1, col2 = st.columns([2, 1])  # wider first column
    col1.write(stat)
    col2.write(points)


st.subheader("Rules:")

st.write('3 week of playoffs. Top 6 make it. Championship weekend 2/28. Playoffs start 2/14. Weeks off: 1/3, 12/27, 12/20, 12/13, 11/29.')
