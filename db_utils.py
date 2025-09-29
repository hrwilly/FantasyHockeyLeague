# db_utils.py
from supabase import create_client
import streamlit as st
import pandas as pd

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

def load_players():
    response = supabase.table("players").select("*").execute()
    return pd.DataFrame(response.data)

def save_players(df):
    # For simplicity, delete all and reinsert
    # (you can optimize this to use updates)
    supabase.table("players").delete().neq("id", 0).execute()
    data = df.to_dict(orient="records")
    supabase.table("players").insert(data).execute()

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
    """Load all teams into a list of dicts (or you can convert to DataFrame)."""
    response = supabase.table("teams").select("*").execute()
    return response.data