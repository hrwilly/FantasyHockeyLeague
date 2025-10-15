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


def save_weekly_points(df):
    """
    Saves (upserts) weekly fantasy points to the 'points' table in Supabase.
    Expects DataFrame columns: Name, team, FantasyPoints.
    """
    if df.empty:
        print("[save_weekly_points] No data to save.")
        return None

    # Copy to avoid modifying original
    df = df.copy()
    df['Week'] = str(date.today())
    

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
    supabase.table("active_rosters").delete().eq("team_name", team_name).eq("week", selected_week).execute()


def submit_roster(all_rows):
    supabase.table("active_rosters").insert(all_rows).execute()
