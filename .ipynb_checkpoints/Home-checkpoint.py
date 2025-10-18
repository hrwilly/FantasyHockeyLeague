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
    ("Penalty minutes", "-0.3 pts each"),
    ("Game Winning Goals", "1 pt each"),
    ("Power Play Goals", "0.5 pts each"),
    ("Short Handed Goals", "1 pts each"),
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

st.markdown("""
- One lineup set for the entire weekend. **MAKE SURE YOU SUBMIT YOUR LINEUP WEEKLY**
- Matchups will be considered for games Thursday through Sunday. No Mon, Tues, Wed games will count.
- We will not play every weekend to account for the time the colleges don't play. The weeks we will not play are Thanksgiving and Winter break: 11/27-11/30, 12/11-12/14, 12/18-12/21, 12/25-12/28, 1/1-1/4.
- Playoffs will be top 6 teams. First place and second place get a first round bye. First week of playoffs is 2/12-2/15. Championship matchup is 2/26-3/1.
- Winner will get choice of Frozen Four merch in Vegas!
- Whoever drafts the Hobey Baker winner will get a Hobey Baker puck.
- DO NOT EDIT ANYONE ELSE'S TEAM PLEASE. We'll play honor system.
""")
