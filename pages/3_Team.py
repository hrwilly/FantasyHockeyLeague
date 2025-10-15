import streamlit as st
import pandas as pd
import db_utils
import time
import numpy as np

st.title("My Team")

# --- Auto-refresh every 5 seconds ---
refresh_interval = 5
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()
if time.time() - st.session_state["last_refresh"] > refresh_interval:
    st.session_state["last_refresh"] = time.time()

# --- Load teams ---
if "teams" not in st.session_state:
    st.session_state.teams = db_utils.load_teams()
teams = st.session_state.teams
if teams.empty:
    st.warning("No teams registered yet.")
    st.stop()

# --- Load players & points into session state only once ---
if "players" not in st.session_state:
    players = db_utils.load_players()
    points = db_utils.load_points()
    weekly = points[points['Week'] == max(points['Week'])][['Name', 'team', 'FantasyPoints']]
    total = points.pivot_table(columns='Week', index=['Name','team'], values='FantasyPoints', aggfunc='mean')
    total['CumulativePts'] = round(total.sum(axis=1), 1)
    total = total.reset_index()[['Name','team','CumulativePts']]
    players = pd.merge(players, weekly, on=['Name','team'], how='left')
    players = pd.merge(players, total, on=['Name','team'], how='left').rename({'FantasyPoints':'WeeklyPts'}, axis=1)
    st.session_state.players = players
players = st.session_state.players

# --- Select your team ---
selected_team = st.selectbox(
    "Select your team:", 
    teams["team_name"], 
    index=teams["team_name"].tolist().index(st.session_state.get("team_name", teams["team_name"].iloc[0]))
)
st.session_state.team_name = selected_team

# --- Build roster function ---
def build_roster(players_df, team_name):
    roster_template = {"F": 6, "D": 4, "G": 2}
    num_bench = 5
    team_players = players_df[players_df["held_by"] == team_name].copy()

    # Create roster placeholders
    roster_rows = []
    for pos, slots in roster_template.items():
        for _ in range(slots):
            roster_rows.append({"Pos.": pos, "Name": "---", "team": "---", "WeeklyPts": "---", "CumulativePts": "---"})
    for _ in range(num_bench):
        roster_rows.append({"Pos.": "Bench", "Name": "---", "team": "---", "WeeklyPts": "---", "CumulativePts": "---"})
    my_roster = pd.DataFrame(roster_rows)

    # Counters for starters per position
    pos_counts = {pos: 0 for pos in roster_template.keys()}
    bench_index = sum(roster_template.values())

    for _, row in team_players.iterrows():
        pos = row["Pos."]
        if pos in roster_template and pos_counts[pos] < roster_template[pos]:
            start_index = sum(
                roster_template[p] for p in list(roster_template.keys())
                if list(roster_template.keys()).index(p) < list(roster_template.keys()).index(pos)
            )
            my_roster.loc[start_index + pos_counts[pos], ["Name", "team", "WeeklyPts", "CumulativePts"]] = row[
                ["Name", "team", "WeeklyPts", "CumulativePts"]
            ]
            pos_counts[pos] += 1
        else:
            # Fill bench sequentially
            my_roster.loc[bench_index, ["Pos.", "Name", "team", "WeeklyPts", "CumulativePts"]] = [
                f"Bench - {pos}", row["Name"], row["team"], row["WeeklyPts"], row["CumulativePts"]
            ]
            bench_index += 1
    return my_roster

# --- Build roster for selected team ---
st.session_state.roster = build_roster(st.session_state.players, selected_team)
st.session_state.starters = st.session_state.roster[~st.session_state.roster["Pos."].str.startswith("Bench") & 
                                                   (st.session_state.roster["Name"] != "---")]
st.session_state.bench = st.session_state.roster[st.session_state.roster["Pos."].str.startswith("Bench") & 
                                                 (st.session_state.roster["Name"] != "---")]

# --- Display roster ---
st.subheader(f"{selected_team}'s Roster")
roster_placeholder = st.empty()
roster_placeholder.table(st.session_state.roster)

# --- Week selection ---
weeks = list(range(1, 16))
selected_week = st.selectbox("Select Week", weeks)

# --- Submit Players ---
if st.button("Submit Players"):
    db_utils.delete_prev_roster(selected_team, selected_week)
    starters = st.session_state.starters
    bench = st.session_state.bench

    starter_rows = [
        {
            "team_name": selected_team,
            "player_name": row["Name"],
            "player_pos": "starter",
            "Pos.": row["Pos."],
            "team": row["team"],
            "week": selected_week
        } for _, row in starters.iterrows()
    ]

    bench_rows = [
        {
            "team_name": selected_team,
            "player_name": row["Name"],
            "player_pos": "bench",
            "Pos.": row["Pos."],
            "team": row["team"],
            "week": selected_week
        } for _, row in bench.iterrows()
    ]

    db_utils.submit_roster(starter_rows + bench_rows)
    st.success(f"✅ Lineup for Week {selected_week} submitted successfully!")

# --- Swap Players ---
st.subheader("Swap Players (Starters ↔ Bench)")
if "swap1" not in st.session_state: st.session_state.swap1 = ""
if "swap2" not in st.session_state: st.session_state.swap2 = ""

# Starter selection
swap1_options = [""] + st.session_state.starters["Name"].tolist()
swap1_index = swap1_options.index(st.session_state.swap1) if st.session_state.swap1 in st.session_state.starters["Name"].tolist() else 0
st.session_state.swap1 = st.selectbox("Select Starter to swap out", swap1_options, index=swap1_index)

# Bench selection filtered by position
if st.session_state.swap1:
    pos1 = st.session_state.roster.loc[st.session_state.roster["Name"] == st.session_state.swap1, "Pos."].values[0]
    swap2_list = st.session_state.bench[st.session_state.bench["Pos."].str.endswith(pos1)]["Name"].tolist()
else:
    swap2_list = []

swap2_options = [""] + swap2_list
swap2_index = swap2_options.index(st.session_state.swap2) if st.session_state.swap2 in swap2_list else 0
st.session_state.swap2 = st.selectbox("Select Bench player to swap in", swap2_options, index=swap2_index)

# Swap action
if st.button("Swap Players") and st.session_state.swap1 and st.session_state.swap2:
    idx1 = st.session_state.players.index[st.session_state.players["Name"] == st.session_state.swap1][0]
    idx2 = st.session_state.players.index[st.session_state.players["Name"] == st.session_state.swap2][0]

    # Swap rows
    st.session_state.players.loc[[idx1, idx2]] = st.session_state.players.loc[[idx2, idx1]].values

    # Fix positions
    pos1 = st.session_state.players.loc[idx1, "Pos."]
    pos2 = st.session_state.players.loc[idx2, "Pos."]
    base_pos = pos1 if not pos1.startswith("Bench") else pos2.split("Bench - ")[-1]
    st.session_state.players.loc[idx1, "Pos."] = base_pos
    st.session_state.players.loc[idx2, "Pos."] = base_pos

    # Rebuild roster
    st.session_state.roster = build_roster(st.session_state.players, selected_team)
    roster_placeholder.table(st.session_state.roster)

    # Update starters and bench
    st.session_state.starters = st.session_state.roster[~st.session_state.roster["Pos."].str.startswith("Bench") &
                                                       (st.session_state.roster["Name"] != "---")]
    st.session_state.bench = st.session_state.roster[st.session_state.roster["Pos."].str.startswith("Bench") &
                                                     (st.session_state.roster["Name"] != "---")]

    # Reset selections
    st.session_state.swap1 = ""
    st.session_state.swap2 = ""
    st.success("✅ Players swapped successfully!")
