import streamlit as st
import pandas as pd
import numpy as np
import db_utils

st.title("🏒 My Team")

# ----------------------------
# Load teams
# ----------------------------
teams = db_utils.load_teams()
if teams.empty:
    st.warning("No teams registered yet.")
    st.stop()

# ----------------------------
# Select team
# ----------------------------
selected_team = st.selectbox("Select your team:", teams["team_name"])

# ----------------------------
# Load base tables
# ----------------------------
players = db_utils.load_players()
points = db_utils.load_points()
lineup_state = db_utils.load_lineup_state(selected_team)

# ----------------------------
# Compute WeeklyPts + CumulativePts (from points table)
# ----------------------------
players_pts = players.copy()

if points is not None and not points.empty and "Week" in points.columns:
    # latest week available in points
    latest_week = int(points["Week"].max())

    # weekly totals for latest week
    weekly = points.loc[points["Week"] == latest_week, ["Name", "team", "FantasyPoints", "Week"]].copy()
    weekly_total = (
        weekly
        .pivot_table(index=["Name", "team"], values="FantasyPoints", aggfunc="sum")
        .reset_index()
        .rename(columns={"FantasyPoints": "WeeklyPts"})
    )

    # cumulative totals across all weeks
    cumulative = (
        points
        .pivot_table(index=["Name", "team"], values="FantasyPoints", aggfunc="sum")
        .reset_index()
        .rename(columns={"FantasyPoints": "CumulativePts"})
    )

    players_pts = players_pts.merge(weekly_total, on=["Name", "team"], how="left")
    players_pts = players_pts.merge(cumulative, on=["Name", "team"], how="left")
else:
    latest_week = None
    players_pts["WeeklyPts"] = 0.0
    players_pts["CumulativePts"] = 0.0

players_pts["WeeklyPts"] = players_pts["WeeklyPts"].fillna(0.0).astype(float)
players_pts["CumulativePts"] = players_pts["CumulativePts"].fillna(0.0).astype(float)

# ----------------------------
# Initialize lineup_state if empty (first time only)
# ----------------------------
roster_template = {"F": 6, "D": 4, "G": 2}

# ----------------------------
# Merge lineup_state with full player columns
#   lineup_state has: team_name, player_name, player_pos, Pos., team
#   players_pts has: ALL players columns + WeeklyPts/CumulativePts
# ----------------------------
team_lineup = lineup_state.merge(
    players_pts,
    left_on="player_name",
    right_on="Name",
    how="left",
    suffixes=("", "_players")
)

# Keep only current team’s owned players in case of stale rows
# (Optional safety: lineup_state should already only contain owned players)
team_lineup = team_lineup[team_lineup["held_by"] == selected_team].copy()

# ----------------------------
# Build ordered starter/bench views
# ----------------------------
starters = team_lineup[team_lineup["player_pos"] == "starter"].copy()
bench = team_lineup[team_lineup["player_pos"] == "bench"].copy()

# order starters by roster template positions
pos_order = {p: i for i, p in enumerate(roster_template.keys())}
starters["__pos_order"] = starters["Pos."].map(pos_order).fillna(999).astype(int)
starters = starters.sort_values(by=["__pos_order", "Pos.", "Name"], ascending=[True, True, True]).drop(columns="__pos_order")

# bench order: by position then name
bench = bench.sort_values(by=["Pos.", "Name"], ascending=[True, True])

# ----------------------------
# Display stacked: Starters then Bench
# Include EVERY column from players + WeeklyPts + CumulativePts
# (We’ll hide helper columns and duplicate join keys)
# ----------------------------
st.subheader(f"{selected_team}'s Lineup")

if latest_week is not None:
    st.caption(f"WeeklyPts = Week {latest_week} totals | CumulativePts = season-to-date")
else:
    st.caption("WeeklyPts/CumulativePts are 0 because there are no saved points yet.")

# Choose columns: "Name" first, then rest of players columns, plus WeeklyPts/CumulativePts
# (players_pts already has WeeklyPts/CumulativePts)
player_cols = list(players_pts.columns)

# Move Name/team/Pos. toward the front for readability
front = [c for c in ["Name", "Pos.", "team", "WeeklyPts", "CumulativePts"] if c in player_cols]
display_cols = front

st.markdown("### Starters")
if starters.empty:
    st.info("No starters set.")
else:
    starters_view = starters[display_cols].copy()

    # formatting
    fmt_cols = {}
    if "WeeklyPts" in starters_view.columns:
        fmt_cols["WeeklyPts"] = "{:.1f}"
    if "CumulativePts" in starters_view.columns:
        fmt_cols["CumulativePts"] = "{:.1f}"

    st.dataframe(
        starters_view.style.format(fmt_cols, na_rep=""),
        use_container_width=True,
        height=420
    )

st.divider()

st.markdown("### Bench")
if bench.empty:
    st.info("No bench players.")
else:
    bench_view = bench[display_cols].copy()

    fmt_cols = {}
    if "WeeklyPts" in bench_view.columns:
        fmt_cols["WeeklyPts"] = "{:.1f}"
    if "CumulativePts" in bench_view.columns:
        fmt_cols["CumulativePts"] = "{:.1f}"

    st.dataframe(
        bench_view.style.format(fmt_cols, na_rep=""),
        use_container_width=True,
        height=200
    )

# ----------------------------
# Swap UI (still works, persists to DB)
# Only allow swaps between same base position
# ----------------------------
st.divider()
st.subheader("🔄 Swap Players (Starter ↔ Bench)")

if starters.empty or bench.empty:
    st.info("You need at least one starter and one bench player to swap.")
    st.stop()

if "swap_out" not in st.session_state:
    st.session_state.swap_out = ""
if "swap_in" not in st.session_state:
    st.session_state.swap_in = ""

swap_out_options = [""] + starters["player_name"].tolist()
swap_out = st.selectbox(
    "Select starter to swap out",
    swap_out_options,
    index=swap_out_options.index(st.session_state.swap_out)
    if st.session_state.swap_out in swap_out_options else 0
)
st.session_state.swap_out = swap_out

# Bench filtered by same Pos.
if swap_out:
    out_pos = starters.loc[starters["player_name"] == swap_out, "Pos."].values[0]
    bench_candidates = bench.loc[bench["Pos."] == out_pos, "player_name"].tolist()
else:
    bench_candidates = []

swap_in_options = [""] + bench_candidates
swap_in = st.selectbox(
    "Select bench player to swap in",
    swap_in_options,
    index=swap_in_options.index(st.session_state.swap_in)
    if st.session_state.swap_in in swap_in_options else 0
)
st.session_state.swap_in = swap_in

if st.button("Swap Players") and swap_out and swap_in:
    db_utils.swap_lineup_state(
        team_name=selected_team,
        player_out=swap_out,
        player_in=swap_in
    )

    st.success("✅ Players swapped successfully!")
    st.session_state.swap_out = ""
    st.session_state.swap_in = ""
    st.rerun()
