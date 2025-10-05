# db_utils.py
from supabase import create_client
import streamlit as st
import pandas as pd
import time
from datetime import date

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


def save_weekly_scoring(df, week=None):
    """
    Upserts weekly fantasy points into the weekly_scores table.
    Expects columns: Name, team, FantasyPoints.
    """
    if df.empty:
        print("[save_weekly_scoring] No data to save.")
        return None

    if week is None:
        week = str(date.today())

    df = df.copy()
    df["Week"] = week

    records = df.to_dict(orient="records")
    print(f"[save_weekly_scoring] Upserting {len(records)} records")

    try:
        response = supabase.table("points")\
            .upsert(records, on_conflict=["Name", "Week"])\
            .execute()

        print("[save_weekly_scoring] Response:", response)
        return response
    except Exception as e:
        print("[save_weekly_scoring] Error:", e)
        return None