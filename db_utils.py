import pandas as pd
import os

PLAYERS_FILE = "players.csv"
TEAMS_FILE = "teams.csv"

def init_data():
    """Initialize CSV files if they don't exist"""
    if not os.path.exists(PLAYERS_FILE):
        df = pd.DataFrame({
            "player": ["Player A", "Player B", "Player C", "Player D"],
            "drafted_by": [None, None, None, None]
        })
        df.to_csv(PLAYERS_FILE, index=False)

    if not os.path.exists(TEAMS_FILE):
        df = pd.DataFrame(columns=["team_name", "manager"])
        df.to_csv(TEAMS_FILE, index=False)

def load_players():
    return pd.read_csv(PLAYERS_FILE)

def save_players(df):
    df.to_csv(PLAYERS_FILE, index=False)

def load_teams():
    return pd.read_csv(TEAMS_FILE)

def save_teams(df):
    df.to_csv(TEAMS_FILE, index=False)
