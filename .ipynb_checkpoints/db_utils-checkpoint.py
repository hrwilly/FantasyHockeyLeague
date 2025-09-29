# db_utils.py
from supabase import create_client
import streamlit as st
import pandas as pd

url = st.secrets["https://gfhcikfciwaepodjxvlt.supabase.co"]
key = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaGNpa2ZjaXdhZXBvZGp4dmx0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkxNzg1ODUsImV4cCI6MjA3NDc1NDU4NX0.vH7BZAbKaTSj1bOAebNvuiWjAtu9cbPZ2skq5cYHiqM"]
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
