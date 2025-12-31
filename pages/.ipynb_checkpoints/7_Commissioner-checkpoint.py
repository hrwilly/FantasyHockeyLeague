import streamlit as st
import pandas as pd
import db_utils

st.title("🏆 Commissioner Tools")

# ======================================================
# WEEK / DAY SELECTION
# ======================================================
selected_week = st.selectbox("Select Week", list(range(1, 16)))
selected_day = st.selectbox("Select Day", list(range(1, 5)))

st.session_state["selected_week"] = selected_week
st.session_state["selected_day"] = selected_day

st.divider()

# ======================================================
# 🔒 LOCK LINEUPS
# ======================================================
st.subheader("🔒 Lock Lineups for Scoring")

st.warning(
    "Locking lineups will snapshot ALL current team lineups.\n\n"
    "This determines starters & bench for scoring and cannot be undone."
)

if st.button("🔒 Lock Lineups for Week"):
    db_utils.lock_weekly_rosters(selected_week)
    st.success(f"✅ Lineups locked for Week {selected_week}")

st.divider()

# ======================================================
# WEEKLY SCORING
# ======================================================
st.subheader("🏁 Run Weekly Scoring")

def get_team_names():
    url = "https://collegehockeyinc.com/teams"
    teams = pd.read_html(url)[0]
    teams = teams["Name"].drop([0, 1, 5, 59]).dropna().reset_index(drop=True)
    return teams.tolist()

def get_current_data(team):
    url = f"https://collegehockeyinc.com/teams/{team}/stats26-overall.php"
    tables = pd.read_html(url)

    offense = tables[0]["Scoring"].copy()
    goalies = tables[1]["Goaltending"].copy()

    offense = offense[offense["Name, Yr"] != "TOTAL"].copy()
    goalies = goalies[goalies["Name, Yr"] != "TOTALS"].copy()

    offense[["Name", "Pos.", "Yr"]] = offense["Name, Yr"].str.split(",", expand=True)
    goalies[["Name", "Yr"]] = goalies["Name, Yr"].str.split(",", expand=True)

    stats = pd.merge(offense, goalies, on=["Name", "Yr"], how="outer", suffixes=("_off", "_goal"))
    stats["GP"] = stats.get("GP_off", pd.Series(dtype=float)).fillna(stats.get("GP_goal", pd.Series(dtype=float)))
    stats = stats.drop(columns=["GP_off", "GP_goal"], errors="ignore")

    for col in [
        "G","A","Shots","PIM","GWG","PPG","SHG","+/-","FOW","FOL","BLK",
        "W","GA","SV","SO"
    ]:
        off = f"{col}_off"
        gol = f"{col}_goal"
        if off in stats.columns and gol in stats.columns:
            stats[col] = stats[off].fillna(stats[gol])
        elif off in stats.columns:
            stats[col] = stats[off]
        elif gol in stats.columns:
            stats[col] = stats[gol]

    stats = stats.drop(columns=[c for c in stats.columns if c.endswith("_off") or c.endswith("_goal")], errors="ignore")
    stats["team"] = team
    stats = stats.set_index(["Name", "team"])

    stats_cols = [
        "GP","G","A","Shots","PIM","GWG","PPG","SHG","+/-","FOW","FOL","BLK",
        "W","GA","SV","SO"
    ]
    for c in stats_cols:
        if c not in stats.columns:
            stats[c] = 0

    return stats[stats_cols].fillna(0)

def compute_fantasy_points(df):
    multipliers = {
        "GP": 0, "G": 2, "A": 1, "Shots": 0.1, "PIM": -0.3, "GWG": 1,
        "PPG": 0.5, "SHG": 1, "+/-": 0.5, "FOW": 0.1,
        "FOL": -0.1, "BLK": 0.5, "W": 4, "GA": -2,
        "SV": 0.2, "SO": 3
    }

    scored = df.copy()
    for col, mult in multipliers.items():
        if col in scored.columns:
            scored[col] = scored[col] * mult

    scored["FantasyPoints"] = scored.sum(axis=1).round(1)
    return scored

if st.button("🏁 Run Weekly Scoring"):
    teams = get_team_names()
    current_cum = pd.DataFrame()

    for team in teams:
        try:
            current_cum = pd.concat([current_cum, get_current_data(team[:-1])])
        except Exception as e:
            st.warning(f"Skipping {team}: {e}")

    last_week = db_utils.load_last_week_stats()
    if last_week is None or last_week.empty:
        last_week = pd.DataFrame(columns=current_cum.columns).set_index(current_cum.index.names)

    last_week = last_week.set_index(["Name", "team"])
    current_cum, last_week = current_cum.align(last_week, join="outer", fill_value=0)

    new_players = current_cum.index.difference(last_week.index)
    weekly_stats = current_cum - last_week
    weekly_stats.loc[new_players] = current_cum.loc[new_players]
    weekly_stats = weekly_stats[(weekly_stats != 0).any(axis=1)]

    weekly_scored = compute_fantasy_points(weekly_stats)

    st.session_state["weekly_scored"] = weekly_scored
    st.session_state["current_cum"] = current_cum

    st.success("✅ Weekly scoring calculated")
    st.dataframe(weekly_scored, use_container_width=True)

# ======================================================
# SAVE WEEKLY SCORING
# ======================================================
if "weekly_scored" in st.session_state and st.button("💾 Save Weekly Scoring"):
    points = (
        st.session_state["weekly_scored"]
        .reset_index()[["Name", "team", "FantasyPoints"]]
    )
    points = points[points["FantasyPoints"] != 0]

    db_utils.save_weekly_points(points, selected_week, selected_day)
    db_utils.save_last_week_stats(st.session_state["current_cum"])

    st.success("✅ Weekly scoring saved")

st.divider()

# ======================================================
# RUN & SAVE MATCHUPS
# ======================================================
st.subheader("⚔️ Run Matchups")

if st.button("🏁 Run Matchups"):
    matchups = db_utils.load_matchups()
    teams_df = db_utils.load_teams()
    rosters = db_utils.load_roster()   # active_roster snapshot
    points = db_utils.load_points()

    matchups = (
        matchups
        .merge(teams_df.rename(columns={"team_name": "home_team", "manager": "manager_1"}), on="home_team")
        .merge(teams_df.rename(columns={"team_name": "away_team", "manager": "manager_2"}), on="away_team")
    )

    week_matchups = matchups[matchups["week"] == selected_week].copy()
    week_rosters = rosters[rosters["week"] == selected_week].copy()
    week_points = points[points["Week"] == selected_week].copy()

    if week_points.empty:
        week_rosters["points"] = 0.0
    else:
        totals = (
            week_points.groupby(["Name", "team"], as_index=False)["FantasyPoints"]
            .sum()
            .rename(columns={"Name": "player_name", "FantasyPoints": "points"})
        )
        week_rosters = week_rosters.merge(totals, on=["player_name", "team"], how="left")
        week_rosters["points"] = week_rosters["points"].fillna(0.0)

    week_matchups["home_team_points"] = 0.0
    week_matchups["away_team_points"] = 0.0

    for i, row in week_matchups.iterrows():
        home = row["home_team"]
        away = row["away_team"]

        home_pts = (
            week_rosters
            .query("team_name == @home and player_pos == 'starter'")["points"]
            .sum()
        )
        away_pts = (
            week_rosters
            .query("team_name == @away and player_pos == 'starter'")["points"]
            .sum()
        )

        week_matchups.loc[i, "home_team_points"] = round(float(home_pts), 1)
        week_matchups.loc[i, "away_team_points"] = round(float(away_pts), 1)

    db_utils.save_weekly_matchups(week_matchups, selected_week)
    st.success("✅ Matchups saved")
    st.dataframe(week_matchups, use_container_width=True)

st.divider()

# ======================================================
# UPDATE STANDINGS
# ======================================================
st.subheader("📊 Update Standings")

if st.button("💾 Save Matchup Results"):
    teams_df = db_utils.load_teams()
    matchups_df = db_utils.load_matchups()
    week_matchups = matchups_df[matchups_df["week"] == selected_week].copy()

    # week_matchups should already have points after save_weekly_matchups
    # If not, this will still work but won't change records meaningfully
    for _, row in week_matchups.iterrows():
        home, away = row["home_team"], row["away_team"]
        hp, ap = float(row.get("home_team_points", 0.0)), float(row.get("away_team_points", 0.0))

        if hp > ap:
            teams_df.loc[teams_df["team_name"] == home, "W"] += 1
            teams_df.loc[teams_df["team_name"] == away, "L"] += 1
        elif ap > hp:
            teams_df.loc[teams_df["team_name"] == away, "W"] += 1
            teams_df.loc[teams_df["team_name"] == home, "L"] += 1

        teams_df.loc[teams_df["team_name"] == home, ["PF", "PA"]] += [hp, ap]
        teams_df.loc[teams_df["team_name"] == away, ["PF", "PA"]] += [ap, hp]

    teams_df = teams_df.sort_values(["W", "L", "PF"], ascending=[False, True, False]).reset_index(drop=True)
    teams_df["Place"] = range(1, len(teams_df) + 1)

    for _, r in teams_df.iterrows():
        db_utils.update_team_record(
            r["team_name"],
            int(r["W"]),
            int(r["L"]),
            float(r["PF"]),
            float(r["PA"]),
            int(r["Place"]),
        )

    st.success(f"✅ Week {selected_week} processed successfully!")

st.divider()

# ======================================================
# OFF-WEEK UPDATE
# ======================================================
st.subheader("🏁 Run off-week")

if st.button("🏁 Run off-week"):
    teams = get_team_names()
    current_cum = pd.DataFrame()

    for team in teams:
        try:
            current_cum = pd.concat([current_cum, get_current_data(team[:-1])])
        except Exception as e:
            st.warning(f"Skipping {team}: {e}")

    db_utils.save_last_week_stats(current_cum)
    st.success("✅ Updated stats between weeks.")
