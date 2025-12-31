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
    return db_utils.load_players_for_team(team_name)

@st.cache_data(ttl=120, show_spinner=False)
def load_points_cached():
    return db_utils.load_points()

@st.cache_data(ttl=2, show_spinner=False)
def load_lineup_state_cached(team_name: str):
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
# LOAD TEAM PLAYERS / POINTS / LINEUP_STATE
# ======================================================
players = load_players_for_team_cached(selected_team)
points = load_points_cached()
lineup_state = load_lineup_state_cached(selected_team)

# ======================================================
# Compute WeeklyPts + CumulativePts for THIS TEAM ONLY (robust + fast)
# ======================================================
players_pts = players.copy()
players_pts = players_pts.drop(columns=["WeeklyPts", "CumulativePts"], errors="ignore")

# Default columns always exist
players_pts["WeeklyPts"] = 0.0
players_pts["CumulativePts"] = 0.0
latest_week = None

if points is not None and not points.empty and "Week" in points.columns:
    latest_week = int(points["Week"].max())

    # Filter points down to this team's roster keys (fast, vectorized)
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

        # Merge results in (no collisions because we already created columns,
        # but we merge into players_pts AFTER defaults; so we overwrite via combine-first)
        players_pts = players_pts.drop(columns=["WeeklyPts", "CumulativePts"], errors="ignore")
        players_pts = players_pts.merge(weekly_total, on=["Name", "team"], how="left")
        players_pts = players_pts.merge(cumulative, on=["Name", "team"], how="left")

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
            "Pos.": pos,
            "team": row["team"],
        })

    if lineup_rows:
        db_utils.save_lineup_state(lineup_rows)

    load_lineup_state_cached.clear()
    lineup_state = load_lineup_state_cached(selected_team)

# ======================================================
# Merge lineup_state + ALL player columns
# ======================================================
team_lineup = lineup_state.merge(
    players_pts,
    left_on="player_name",
    right_on="Name",
    how="left"
)

# Drop stale lineup_state rows that don't join
team_lineup = team_lineup[team_lineup["Name"].notna()].copy()

starters = team_lineup[team_lineup["player_pos"] == "starter"].copy()
bench = team_lineup[team_lineup["player_pos"] == "bench"].copy()

# Order starters by position F/D/G then name
pos_order = {p: i for i, p in enumerate(roster_template.keys())}
starters["__pos_order"] = starters["Pos."].map(pos_order).fillna(999).astype(int)
starters = starters.sort_values(by=["__pos_order", "Pos.", "Name"]).drop(columns="__pos_order")
bench = bench.sort_values(by=["Pos.", "Name"])

# Display columns: every players column + WeeklyPts/CumulativePts
player_cols = list(players_pts.columns)
front = [c for c in ["Name", "Pos.", "team", "WeeklyPts", "CumulativePts", "held_by"] if c in player_cols]
rest = [c for c in player_cols if c not in front]
display_cols = front + rest

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

    load_lineup_state_cached.clear()
    st.success("✅ Players swapped successfully!")
    st.session_state.swap_out = ""
    st.session_state.swap_in = ""
    st.rerun()
