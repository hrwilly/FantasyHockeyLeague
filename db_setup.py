# db_setup.py
import sqlite3

# Connect to (or create) database
conn = sqlite3.connect("fantasy_league.db")
c = conn.cursor()

# Create teams table
c.execute("""
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT UNIQUE NOT NULL
)
""")

# Create players table
c.execute("""
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Pos TEXT,
    team TEXT,
    Ht TEXT,
    Wt REAL,
    drafted_by TEXT,
    Pick_Number INTEGER
)
""")

conn.commit()
conn.close()
print("Database and tables are ready!")
