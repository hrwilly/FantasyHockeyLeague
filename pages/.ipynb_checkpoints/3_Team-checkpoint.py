import streamlit as st
import pandas as pd
import numpy as np
import db_utils

st.title("🏒 My Team")

# ======================================================
# CACHED LOADERS
# ======================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_teams_cached():
    return db_utils.load_teams()

@st.cache_data(ttl=300, show_spinner=False)
def load_players_for_team_cached(team_name: str):
    # Requires db_utils.load_players_for_team(team_name)
    return db_utils.load_players_for_team(team_name)

@st.cache_data(ttl=120, show_spinner=False)
def load_points_cached():
    return db_utils.load_points()

@st.cache_data(ttl=120, show_spinner=False)
def load_last_week_stats_cached():
    return db_utils.load_last_week_stats()

@st.cache_data(ttl=2, show_spinner=False)
def load_lineup_state_cached(team_name: str):
    # Requires db_utils.load_lineup_state(team_name)
    return db_utils.load_lineup_state(team_name)

with st.sidebar:
    if st.button("🔄 Refresh cached data"):
        st.cache_data.clear()
        st.rerun()

# ======================================================
# LOAD TEAMS / SELECT TEAM
# ======================================================
teams = load_teams_cached()
if teams.empty:
    st.warning("No teams registered yet.")
    st.stop()

selected_team = st.selectbox("Select your team:", teams["team_name"])

# ======================================================
# TOGGLE: SHOW STATS COLUMNS
# (Put this near the top so it doesn't move around)
# ======================================================
show_stats = st.toggle("Show last week stats columns", value=True)

# ======================================================
# LOAD TEAM PLAYERS / POINTS / STATS / LINEUP_STATE
# ======================================================
players_team = load_players_for_team_cached(selected_team)
points = load_points_cached()
stats = load_last_week_stats_cached()
lineup_state = load_lineup_state_cached(selected_team)

# Merge last_week_stats onto this team's players
if stats is not None and not stats.empty:
    players_team = players_team.merge(stats, on=["Name", "team"], how="left")

# ======================================================
# Compute WeeklyPts + CumulativePts for THIS TEAM ONLY
# ======================================================
players_pts = players_team.copy()
players_pts = players_pts.drop(columns=["WeeklyPts", "CumulativePts"], errors="ignore")

latest_week = None

if points is not None and not points.empty and "Week" in points.columns:
    latest_week = int(points["Week"].max())

    roster_keys = players_pts[["Name", "team"]].drop_duplicates()
    pts_small = points.merge(roster_keys, on=["Name", "team"], how="inner")

    if not pts_small.empty:
        weekly = pts_small.loc[pts_small["Week"] == latest_week, ["Name", "team", "FantasyPoints"]]
        weekly_total = (
            weekly.groupby(["Name", "team"], as_index=False)["FantasyPoints"]
            .sum()
            .rename(columns={"FantasyPoints": "WeeklyPts"})
        )

        cumulative = (
            pts_small.groupby(["Name", "team"], as_index=False)["FantasyPoints"]
            .sum()
            .rename(columns={"FantasyPoints": "CumulativePts"})
        )

        players_pts = players_pts.merge(weekly_total, on=["Name", "team"], how="left")
        players_pts = players_pts.merge(cumulative, on=["Name", "team"], how="left")

# Ensure columns always exist
if "WeeklyPts" not in players_pts.columns:
    players_pts["WeeklyPts"] = 0.0
if "CumulativePts" not in players_pts.columns:
    players_pts["CumulativePts"] = 0.0

players_pts["WeeklyPts"] = players_pts["WeeklyPts"].fillna(0.0).astype(float).round(1)
players_pts["CumulativePts"] = players_pts["CumulativePts"].fillna(0.0).astype(float).round(1)

# ======================================================
# Initialize lineup_state if empty (first time only)
# ======================================================
roster_template = {"F": 6, "D": 4, "G": 2}

if lineup_state is None or lineup_state.empty:
    team_players = players_pts.copy()

    lineup_rows = []
    pos_counts = {pos: 0 for pos in roster_template}

    team_players = team_players.sort_values(by=["Pos.", "Name"], ascending=[True, True])

    for _, row in team_players.iterrows():
        pos = row["Pos."]
        is_starter = (pos in roster_template) and (pos_counts[pos] < roster_template[pos])
        if is_starter:
            pos_counts[pos] += 1

        lineup_rows.append({
            "team_name": selected_team,
            "player_name": row["Name"],
            "player_pos": "starter" if is_starter else "bench",
        })

    if lineup_rows:
        db_utils.save_lineup_state(lineup_rows)

    load_lineup_state_cached.clear()
    lineup_state = load_lineup_state_cached(selected_team)

# ======================================================
# Merge lineup_state + player data (avoid Pos./team collisions)
# ======================================================
lineup_state_small = lineup_state[["team_name", "player_name", "player_pos"]].copy()

team_lineup = lineup_state_small.merge(
    players_pts,
    left_on="player_name",
    right_on="Name",
    how="inner"
)

pos_col = "Pos."

starters = team_lineup[team_lineup["player_pos"] == "starter"].copy()
bench = team_lineup[team_lineup["player_pos"] == "bench"].copy()

# Order starters by position F/D/G then name
pos_order = {"F": 0, "D": 1, "G": 2}
starters["__pos_order"] = starters[pos_col].map(pos_order).fillna(999).astype(int)
starters = starters.sort_values(by=["__pos_order", pos_col, "Name"]).drop(columns="__pos_order")
bench = bench.sort_values(by=[pos_col, "Name"])

# ======================================================
# Display columns: base + last_week_stats stat columns (toggle)
# ======================================================
base_cols = ["Name", "Pos.", "team", "WeeklyPts", "CumulativePts"]
stat_cols = [c for c in stats.columns if c not in ["Name", "team"]] if stats is not None and not stats.empty else []
display_cols = base_cols + stat_cols if show_stats else base_cols

# ======================================================
# Display stacked tables
# ======================================================
st.subheader(f"{selected_team}'s Lineup")
if latest_week is not None:
    st.caption(f"WeeklyPts = Week {latest_week} totals | CumulativePts = season-to-date")
else:
    st.caption("WeeklyPts/CumulativePts are 0 because there are no saved points yet.")

st.markdown("### Starters")
if starters.empty:
    st.info("No starters set.")
else:
    st.dataframe(starters[display_cols], use_container_width=True, height=480)

st.divider()

st.markdown("### Bench")
if bench.empty:
    st.info("No bench players.")
else:
    st.dataframe(bench[display_cols], use_container_width=True, height=220)

# ======================================================
# Swap UI
# ======================================================
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

# Bench candidates filtered by same position
if swap_out:
    out_pos = starters.loc[starters["player_name"] == swap_out, pos_col].values[0]
    bench_candidates = bench.loc[bench[pos_col] == out_pos, "player_name"].tolist()
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

    load_lineup_state_cached.clear()
    st.success("✅ Players swapped successfully!")
    st.session_state.swap_out = ""
    st.session_state.swap_in = ""
    st.rerun()
