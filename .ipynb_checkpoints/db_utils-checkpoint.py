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

def load_teams():
    response = supabase.table("teams").select("*").execute()
    return pd.DataFrame(response.data)

def save_teams(df):
    supabase.table("teams").delete().neq("id", 0).execute()
    data = df.to_dict(orient="records")
    supabase.table("teams").insert(data).execute()
