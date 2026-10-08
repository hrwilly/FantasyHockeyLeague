import streamlit as st
import pandas as pd
import db_utils

st.title("🏆 Commissioner Tools")

# ======================================================
# WEEK / DAY SELECTION
# ======================================================
selected_week = st.selectbox("Select Week", list(range(1, 17)))
selected_day = st.selectbox("Select Day", list(range(1, 5)))

st.session_state["selected_week"] = selected_week
st.session_state["selected_day"] = selected_day

st.divider()

# ======================================================
# 🔒 LOCK LINEUPS
# ======================================================
st.subheader("🔒 Lock Lineups for Current Week Matchups")

if st.button("🔒 Lock Lineups for Week"):
    db_utils.lock_weekly_rosters(selected_week)
    st.success(f"✅ Lineups locked for Week {selected_week}")

st.divider()

# ======================================================
# WEEKLY SCORING
# ======================================================
st.subheader("🏁 Run Last Night Player Scoring")

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

    # GP is in both tables with suffixes; prefer offense then goalie
    gp_off = stats["GP_off"] if "GP_off" in stats.columns else pd.Series(dtype=float)
    gp_goal = stats["GP_goal"] if "GP_goal" in stats.columns else pd.Series(dtype=float)
    stats["GP"] = gp_off.fillna(gp_goal)
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

if st.button("🏁 Run Last Night Player Scoring"):
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
if 'weekly_scored' in st.session_state and st.button('💾 Save Scoring'):
    st.markdown('Saving points...')

    points = st.session_state['weekly_scored']
    points = points.reset_index()
    points = points[['Name', 'team', 'FantasyPoints']]
    points = points[points['FantasyPoints'] != 0]

    current_cum = st.session_state['current_cum']

    db_utils.save_weekly_points(points, st.session_state.selected_week, st.session_state.selected_day)
    db_utils.save_last_week_stats(current_cum)
    st.success(f"✅ Weekly scoring saved for Week {st.session_state.selected_week}, Day {st.session_state.selected_day}.")

st.divider()
st.subheader("🏁 Run Matchup Results")

if st.button('🏁 Run Matchup Results'):
    matchups_df = db_utils.load_matchups()
    managers = db_utils.load_teams()
    rosters_df = db_utils.load_roster()
    points = db_utils.load_points()

    st.session_state['team_stats'] = managers
    
    matchups_df = (
            matchups_df
            .merge(managers.rename(columns={"team_name": "home_team", "manager": "manager_1"}), on="home_team")
            .merge(managers.rename(columns={"team_name": "away_team", "manager": "manager_2"}), on="away_team")
        )

    selected_week = st.session_state.selected_week
    week_matchups = matchups_df[matchups_df["week"] == selected_week]
    week_rosters = rosters_df[rosters_df['week'] == selected_week]
    week_points = points[points['Week'] == selected_week]

    weekly = points[points['Week'] == selected_week][['Name', 'team', 'FantasyPoints', 'Week']]
    weekly_total = weekly.pivot_table(columns='Week', index=['Name','team'], values='FantasyPoints', aggfunc='sum')
    weekly_total['points'] = round(weekly_total.sum(axis=1), 1)
    weekly_total = weekly_total.reset_index()[['Name', 'team', 'points']]

    if len(week_points) != 0:
        week_rosters = week_rosters.merge(weekly_total.rename(columns = {'Name' : 'player_name'}), on = ['player_name', 'team'], how = 'left')
    else:
        week_rosters['points'] = [0] * len(week_rosters)

    # Initialize new columns
    week_matchups["home_team_points"] = 0.0
    week_matchups["away_team_points"] = 0.0
    
    # Loop through each matchup and sum starter points
    for idx, row in week_matchups.iterrows():
        home_team = row["home_team"]
        away_team = row["away_team"]
    
        home_points = (
            week_rosters
            .query("team_name == @home_team and player_pos == 'starter'")
            ["points"]
            .fillna(0)
            .sum()
        )
    
        away_points = (
            week_rosters
            .query("team_name == @away_team and player_pos == 'starter'")
            ["points"]
            .fillna(0)
            .sum()
        )
    
        week_matchups.loc[idx, "home_team_points"] = round(home_points, 1)
        week_matchups.loc[idx, "away_team_points"] = round(away_points, 1)

    db_utils.save_weekly_matchups(week_matchups, selected_week)
    st.success(f"✅ Weekly matchup scores saved for Week {st.session_state.selected_week}")

    st.dataframe(week_matchups[['week', 'home_team', 'away_team', 'home_team_points', 'away_team_points']], hide_index = True)

    st.session_state['weekly_matchups'] = week_matchups

if 'weekly_matchups' in st.session_state and st.button('💾 Save Matchup Results'):

    st.write(f"Processing week {selected_week}...")
    week_matchups = st.session_state.weekly_matchups
    teams_df = st.session_state.team_stats

    # We'll update each team cumulatively
    for _, row in week_matchups.iterrows():
        home_team = row["home_team"]
        away_team = row["away_team"]
        home_points = row["home_team_points"]
        away_points = row["away_team_points"]

        # Get current team records
        home_rec = teams_df.loc[teams_df["team_name"] == home_team].iloc[0]
        away_rec = teams_df.loc[teams_df["team_name"] == away_team].iloc[0]

        # Extract current stats
        home_W, home_L, home_PF, home_PA = home_rec["W"], home_rec["L"], home_rec["PF"], home_rec["PA"]
        away_W, away_L, away_PF, away_PA = away_rec["W"], away_rec["L"], away_rec["PF"], away_rec["PA"]

        # Update PF/PA
        home_PF += home_points
        home_PA += away_points
        away_PF += away_points
        away_PA += home_points

        # Determine winner/loser
        if home_points > away_points:
            home_W += 1
            away_L += 1
        elif away_points > home_points:
            away_W += 1
            home_L += 1

        # ✅ Update local dataframe
        teams_df.loc[teams_df["team_name"] == home_team, ["W", "L", "PF", "PA"]] = [home_W, home_L, home_PF, home_PA]
        teams_df.loc[teams_df["team_name"] == away_team, ["W", "L", "PF", "PA"]] = [away_W, away_L, away_PF, away_PA]

    teams_df = teams_df.sort_values(by=["W", "L", "PF"], ascending=[False, True, False]).reset_index(drop=True)
    teams_df["Place"] = range(1, len(teams_df) + 1)

    # --- Push all team updates once ---
    for _, row in teams_df.iterrows():
        db_utils.update_team_record(
            row["team_name"],
            W=int(row["W"]),
            L=int(row["L"]),
            PF=float(row["PF"]),
            PA=float(row["PA"]),
            Place=int(row["Place"])
        )

    st.success(f"✅ Week {selected_week} processed successfully!")

st.divider()
st.subheader('🏁 Run mid-week scoring')

if st.button('🏁 Run mid-week scoring'):

    coll_teams = get_team_names()
    current_cum = pd.DataFrame()

    for team in coll_teams:
        try:
            team_points = get_current_data(team[:-1])
            current_cum = pd.concat([current_cum, team_points])
        except Exception as e:
            st.warning(f"Skipping team {team[:-1]}: {e}")

    db_utils.save_last_week_stats(current_cum)

    st.success(f"✅ Updated stats between weeks.")
