import streamlit as st
import pandas as pd
import db_utils
from streamlit_autorefresh import st_autorefresh

st.title("🏒 Fantasy Draft Room")

# --- Auto-refresh every 5 seconds ---
st_autorefresh(interval=50000, key="draft_autorefresh")

# --- Load teams ---
if "teams" not in st.session_state:
    st.session_state.teams = db_utils.load_teams()
teams = st.session_state.teams
if teams.empty:
    st.warning("No teams registered yet. Go to the Register page first.")
    st.stop()

# --- Load draft board ---
def load_draft_board():
    df = db_utils.load_draft_board()
    if df is None or df.empty:
        df = pd.DataFrame(columns=["Round", "Pick", "Name", "team", "Pos.", "FantasyTeam"])
    return df.sort_values(by=["Round", "Pick"])

st.session_state.draft_board = load_draft_board()
draft_board = st.session_state.draft_board


# --- Load players ---
st.session_state.players = db_utils.load_players()
players = st.session_state.players
stats = db_utils.load_last_week_stats()
players = pd.merge(players, stats, on = ['Name', 'team'], how = 'left')

# --- Determine current pick ---
next_pick_row = draft_board[draft_board["Name"].isna()].head(1)

# --- Upcoming Draft Order ---
st.subheader("Upcoming Draft Order")
upcoming_picks = draft_board[draft_board["Name"].isna()].head(5)
if upcoming_picks.empty:
    st.info("All upcoming picks have been drafted!")
else:
    cols = st.columns(len(upcoming_picks))
    for col, (_, row) in zip(cols, upcoming_picks.iterrows()): 
        short_name = row["FantasyTeam"] 
        col.markdown( f""" <div style=" background-color:#4CAF50; 
                                        color:white; 
                                        padding:10px; 
                                        text-align:center; 
                                        border-radius:5px; 
                                        font-weight:bold; "> 
                                        {short_name}<br>R{row['Round']} 
                                        P{row['Pick']} </div> """, unsafe_allow_html=True )
# --- Select your team ---
st.session_state["team_name"] = st.selectbox(
    "Select your team:",
    ['Mac', 'Take a Lachance on me', 'What the Helena', 'Jordan', 'Meth Rhett', 'Zeev Buium', 'HYHusky', 'Graham', 'All Aboard the Cole Train', 'Puck Stops Here', 'LaSoiréeDuHockeyMolson', 'Mike is gonna Ryder Dyck']
)
selected_team = st.session_state["team_name"]

# --- Available players ---
available_players = players[players["held_by"].isna()].copy()
available_players = available_players.sort_values(by="Draft Round", key=lambda col: pd.to_numeric(col, errors="coerce"), na_position="last")

st.subheader("Available Players")
if available_players.empty:
    st.warning("No available players left!")
else:
    st.dataframe(available_players.drop('held_by', axis=1).set_index(['Name', 'Pos.', 'team']), width='stretch')

# --- Draft Controls ---
st.subheader("Draft Controls")

available_players = players[players["held_by"].isna()].copy()
available_players = available_players.sort_values(by="Draft Round", key=lambda col: pd.to_numeric(col, errors="coerce"), na_position="last")

if next_pick_row.empty:
    st.info("Draft complete! No picks remaining.")
    can_draft = False
else:
    next_team_to_pick = next_pick_row.iloc[0]["FantasyTeam"]
    can_draft = (selected_team == next_team_to_pick)

if can_draft:
    available_players["label"] = available_players.apply(
        lambda row: f"{row['Name']} — {row['Pos.']} — {row['team']}", axis=1
    )
    label_to_name = dict(zip(available_players["label"], available_players["Name"]))

    selected_label = st.selectbox(
        f"{selected_team}, select a player to draft:",
        options=available_players["label"].tolist(),
        key="player_select_dropdown"
    )
    chosen_player = label_to_name[selected_label]

    if st.button("Draft Player", key="draft_player_button"):
        # --- Update players ---
        idx_players = players["Name"] == chosen_player
        players.loc[idx_players, "held_by"] = selected_team
        st.session_state.players = players.copy()

        # --- Get player info ---
        player_info = players.loc[idx_players].iloc[0]

        # --- Update DraftBoard in session state ---
        idx_board = (draft_board["Round"] == next_pick_row.iloc[0]["Round"]) & \
                    (draft_board["Pick"] == next_pick_row.iloc[0]["Pick"])
        draft_board.loc[idx_board, ["Name", "Pos.", "team", "FantasyTeam"]] = [
            player_info["Name"],
            player_info["Pos."],
            player_info["team"],
            selected_team
        ]
        st.session_state.draft_board = draft_board.copy()

        # --- Update DraftBoard in Supabase ---
        db_utils.update_draft_pick_full(
            round_number=next_pick_row.iloc[0]["Round"],
            pick_number=next_pick_row.iloc[0]["Pick"],
            name=player_info["Name"],
            pos=player_info["Pos."],
            team=player_info["team"],
            fantasy_team=selected_team
        )
        db_utils.save_player(players.loc[idx_players].iloc[0])

        st.success(f"{selected_team} drafted {chosen_player}!")
else:
    if not next_pick_row.empty:
        st.info(f"It is not your turn. Next pick: {next_pick_row.iloc[0]['FantasyTeam']}")

# --- Roster Display ---
st.subheader(f"{selected_team} Roster")
roster_template = {"F": 6, "D": 4, "G": 2}
num_bench = 5

def build_team_roster(players, team_name):
    my_team_players = players[players["held_by"] == team_name]
    roster_rows = []
    for pos, slots in roster_template.items():
        for _ in range(slots):
            roster_rows.append({"Pos.": pos, "Name": "---", "team": "---", "Yr.": "---", "Ht.": "---", "Wt.": "---"})
    for _ in range(num_bench):
        roster_rows.append({"Pos.": "Bench", "Name": "---", "team": "---", "Yr.": "---", "Ht.": "---", "Wt.": "---"})
    my_roster = pd.DataFrame(roster_rows)
    pos_counts = {pos: 0 for pos in roster_template.keys()}

    for _, row in my_team_players.iterrows():
        pos = row["Pos."]
        if pos in roster_template and pos_counts[pos] < roster_template[pos]:
            index = sum([roster_template[p] for p in roster_template
                         if list(roster_template.keys()).index(p) < list(roster_template.keys()).index(pos)]) + pos_counts[pos]
            my_roster.loc[index, ["Name", "team", "Yr.", "Ht.", "Wt."]] = row[["Name", "team", "Yr.", "Ht.", "Wt."]]
            pos_counts[pos] += 1
        else:
            for i in range(len(my_roster)):
                if my_roster.loc[i, "Pos."].startswith("Bench") and my_roster.loc[i, "Name"] == "---":
                    my_roster.loc[i, "Pos."] = f"Bench - {pos}"
                    my_roster.loc[i, ["Name", "team", "Yr.", "Ht.", "Wt."]] = row[["Name", "team", "Yr.", "Ht.", "Wt."]]
                    break
    return my_roster

team_roster = build_team_roster(players, selected_team)
st.table(team_roster)


# --- Draft Board Display ---
st.subheader("Draft Board")
if not draft_board.empty:
    st.dataframe(
        draft_board[draft_board['Name'].notnull()][["Round", "Pick", "Name", "Pos.", "team", "FantasyTeam"]],
        width='stretch'
    )
else:
    st.info("No players have been drafted yet.")