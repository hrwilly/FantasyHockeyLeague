# db_utils.py
from supabase import create_client
import streamlit as st
import pandas as pd
import time
from datetime import date
from httpx import ReadError

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

def get_team_by_name(team_name: str):
    """Return team row if it exists, otherwise None."""
    response = supabase.table("teams").select("*").eq("team_name", team_name).execute()
    if response.data:
        return response.data[0]
    return None

def add_team(team_name: str, manager: str):
    """Insert a new team into the database."""
    supabase.table("teams").insert({
        "team_name": team_name,
        "manager": manager
    }).execute()

def load_teams():
    res = supabase.table("teams").select("*").execute()
    return pd.DataFrame(res.data)

def load_players(batch_size=100, max_retries=3, delay=2):
    start = 0
    end = batch_size - 1
    all_rows = []

    while True:
        try:
            for attempt in range(max_retries):
                try:
                    response = supabase.table("players").select("*").range(start, end).execute()
                    rows = response.data
                    break  # Success: exit retry loop
                except ReadError as e:
                    time.sleep(delay)
            else:
                break  # Break outer loop if all retries failed

            if not rows:
                break  # No more data

            all_rows.extend(rows)
            start += batch_size
            end += batch_size

        except Exception as e:
            break

    return pd.DataFrame(all_rows)

# --- Load the full draft board ---
def load_draft_board() -> pd.DataFrame:
    """
    Pulls the DraftBoard table from Supabase and returns a DataFrame.
    Columns: Round, Pick, Name, team, Pos., FantasyTeam
    """
    response = supabase.table("DraftBoard").select("*").execute()
    df = pd.DataFrame(response.data)
    return df

def update_draft_pick_full(round_number, pick_number, name, pos, team, fantasy_team):
    supabase.table("DraftBoard").update({
        "Name": name,
        "Pos.": pos,
        "team": team,
        "FantasyTeam": fantasy_team
    }).eq("Round", round_number).eq("Pick", pick_number).eq("FantasyTeam", fantasy_team).execute()

def save_player(row):
    row_clean = row.where(pd.notna(row), None)
    supabase.table("players").upsert(row_clean.to_dict()).execute()

def load_last_week_stats(batch_size=100, max_retries=3, delay=2):
    start = 0
    end = batch_size - 1
    all_rows = []

    while True:
        try:
            for attempt in range(max_retries):
                try:
                    response = supabase.table("last_week_stats").select("*").range(start, end).execute()
                    rows = response.data
                    break  # Success: exit retry loop
                except ReadError as e:
                    time.sleep(delay)
            else:
                break  # Break outer loop if all retries failed

            if not rows:
                break  # No more data

            all_rows.extend(rows)
            start += batch_size
            end += batch_size

        except Exception as e:
            break

    return pd.DataFrame(all_rows)


def save_last_week_stats(df: pd.DataFrame):
    if df.empty:
        return

    df = df.reset_index()
    supabase.table("last_week_stats").delete().neq("Name", "").execute()
    data = df.to_dict(orient="records")
    supabase.table("last_week_stats").insert(data).execute()


def save_weekly_points(df, week, day):
    """
    Saves (upserts) weekly fantasy points to the 'points' table in Supabase.
    Expects DataFrame columns: Name, team, FantasyPoints.
    """
    if df.empty:
        print("[save_weekly_points] No data to save.")
        return None

    # Copy to avoid modifying original
    df = df.copy()
    df['Week'] = week
    df['Day'] = day
    
    # Convert to list of dicts for Supabase
    records = df.to_dict(orient="records")
    supabase.table("points").upsert(records).execute()

def load_points(batch_size=100, max_retries=3, delay=2):
    start = 0
    end = batch_size - 1
    all_rows = []

    while True:
        try:
            for attempt in range(max_retries):
                try:
                    response = supabase.table("points").select("*").range(start, end).execute()
                    rows = response.data
                    break  # Success: exit retry loop
                except ReadError as e:
                    time.sleep(delay)
            else:
                break  # Break outer loop if all retries failed

            if not rows:
                break  # No more data

            all_rows.extend(rows)
            start += batch_size
            end += batch_size

        except Exception as e:
            break

    return pd.DataFrame(all_rows)

def load_matchups():

    data = supabase.table("matchups").select("*").execute().data
    return pd.DataFrame(data)

def delete_prev_roster(team_name, selected_week):
    supabase.table("active_roster").delete().eq("team_name", team_name).eq("week", selected_week).execute()


def submit_roster(all_rows):
    supabase.table("active_roster").insert(all_rows).execute()

def load_roster():
    table = supabase.table("active_roster")
    page_size = 1000
    start = 0
    all_rows = []

    while True:
        resp = table.select("*").range(start, start + page_size - 1).execute()
        batch = resp.data

        if not batch:
            break

        all_rows.extend(batch)
        start += page_size

        # Stop when fewer than page_size rows are returned
        if len(batch) < page_size:
            break

    return pd.DataFrame(all_rows)

def save_weekly_matchups(week_matchups: pd.DataFrame, week_num):
    """
    Saves weekly matchup results (Week, home_team, away_team, home_team_points, away_team_points)
    into the Supabase 'Matchups' table.
    """

    # --- Select only the needed columns ---
    upload_cols = ["week", "home_team", "away_team", "home_team_points", "away_team_points"]
    upload_df = week_matchups[upload_cols].copy()

    # --- Convert to list of dicts ---
    records = upload_df.to_dict(orient="records")

    # --- Delete any existing records for that week (to prevent duplicates) ---
    supabase.table("matchups").delete().eq("week", week_num).execute()

    # --- Insert new records ---
    supabase.table("matchups").insert(records).execute()

def update_team_record(team_name, W=None, L=None, PF=None, PA=None, Place=None):
    """Update individual team record values in Supabase."""
    updates = {}
    if W is not None:
        updates["W"] = int(W)
    if L is not None:
        updates["L"] = int(L)
    if PF is not None:
        updates["PF"] = float(PF)
    if PA is not None:
        updates["PA"] = float(PA)
    if Place is not None:
        updates["Place"] = int(Place)

    if updates:
        supabase.table("teams").update(updates).eq("team_name", team_name).execute()

    
def load_lineup_state(team_name):
    resp = (
        supabase
        .table("lineup_state")
        .select("*")
        .eq("team_name", team_name)
        .execute()
    )
    return pd.DataFrame(resp.data)

def save_lineup_state(rows):
    """
    rows: list of dicts
    """
    supabase.table("lineup_state").upsert(rows).execute()

def swap_lineup_state(team_name, player_out, player_in):

    supabase.table("lineup_state").update(
        {"player_pos": "bench"}
    ).eq("team_name", team_name) \
     .eq("player_name", player_out) \
     .execute()

    supabase.table("lineup_state").update(
        {"player_pos": "starter"}
    ).eq("team_name", team_name) \
     .eq("player_name", player_in) \
     .execute()

def lock_weekly_rosters(week):
    resp = supabase.table("lineup_state").select("*").execute()
    lineup = resp.data

    if not lineup:
        return

    supabase.table("active_roster").delete().eq("week", week).execute()

    locked = [
        {**row, "week": week}
        for row in lineup
    ]

    supabase.table("active_roster").insert(locked).execute()

def add_drop_player(
    team_name,
    add_player,
    drop_player,
    add_player_pos,
    add_player_team,
    starter=False
):
    """
    Handles add/drop consistently across players + lineup_state
    """

    # --- Update ownership ---
    supabase.table("players").update(
        {"held_by": team_name}
    ).eq("Name", add_player).execute()

    supabase.table("players").update(
        {"held_by": None}
    ).eq("Name", drop_player).execute()

    # --- Remove dropped player from lineup ---
    supabase.table("lineup_state").delete() \
        .eq("team_name", team_name) \
        .eq("player_name", drop_player) \
        .execute()

    # --- Insert added player into lineup ---
    supabase.table("lineup_state").upsert({
        "team_name": team_name,
        "player_name": add_player,
        "player_pos": "starter" if starter else "bench",
        "Pos.": add_player_pos,
        "team": add_player_team
    }).execute()

def load_players_for_team(team_name: str, batch_size=500, max_retries=3, delay=1):
    """
    Loads only players owned by a single fantasy team (players.held_by == team_name).
    Uses pagination for safety but the result set should be small.
    """
    start = 0
    end = batch_size - 1
    all_rows = []

    while True:
        rows = None

        for attempt in range(max_retries):
            try:
                resp = (
                    supabase
                    .table("players")
                    .select("*")
                    .eq("held_by", team_name)
                    .range(start, end)
                    .execute()
                )
                rows = resp.data
                break
            except ReadError:
                time.sleep(delay)

        # If request never succeeded, stop
        if rows is None:
            break

        if not rows:
            break

        all_rows.extend(rows)

        # advance pagination
        start += batch_size
        end += batch_size

        # stop if last page
        if len(rows) < batch_size:
            break

    return pd.DataFrame(all_rows)
