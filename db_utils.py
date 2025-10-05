# db_utils.py
from supabase import create_client
import streamlit as st
import pandas as pd
import time

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

def load_players():
    res = supabase.table("players").select("*").execute()
    return pd.DataFrame(res.data)

def save_player(row):
    row_clean = row.where(pd.notna(row), None)
    supabase.table("players").upsert(row_clean.to_dict()).execute()

def load_last_week_stats():
    res = supabase.table("last_week_stats").select("*").execute()
    if res.data:
        return pd.DataFrame(res.data)
    return pd.DataFrame()

def save_last_week_stats(df: pd.DataFrame):
    if df.empty:
        return
    data = df.to_dict(orient="records")
    supabase.table("last_week_stats").upsert(data).execute()


def save_weekly_scores(df):
    """
    Save a DataFrame of weekly fantasy scores to the database.
    Expected columns: Name, Team, FantasyPoints
    """
    records = df.to_dict(orient="records")
    if not records:
        return None

    # Optional: Clear previous scores if you only keep latest week
    supabase.table("points").delete().neq("Name", "").execute()

    # Insert new scores
    response = supabase.table("points").insert(records).execute()
    return response

