import streamlit as st
import pandas as pd
import db_utils

st.title("🏒 My Team")

# ----------------------------
# Load teams
# ----------------------------
teams = db_utils.load_teams()

if teams.empty:
    st.warning("No teams registered yet.")
    st.stop()

# ----------------------------
# Select team
# ----------------------------
selected_team = st.selectbox(
    "Select your team:",
    teams["team_name"]
)

# ----------------------------
# Load players + lineup state
# ----------------------------
players = db_utils.load_players()
lineup_state = db_utils.load_lineup_state(selected_team)

# ----------------------------
# Initialize lineup_state if empty
# ----------------------------
roster_template = {"F": 6, "D": 4, "G": 2}
num_bench = 5

if lineup_state.empty:
    team_players = players[players["held_by"] == selected_team].copy()

    lineup_rows = []
    pos_counts = {pos: 0 for pos in roster_template}

    for _, row in team_players.iterrows():
        pos = row["Pos."]

        if pos in roster_template and pos_counts[pos] < roster_template[pos]:
            player_pos = "starter"
            pos_counts[pos] += 1
        else:
            player_pos = "bench"

        lineup_rows.append({
            "team_name": selected_team,
            "player_name": row["Name"],
            "player_pos": player_pos,
            "Pos.": pos,
            "team": row["team"]
        })

    if lineup_rows:
        db_utils.save_lineup_state(lineup_rows)
        lineup_state = db_utils.load_lineup_state(selected_team)

# ----------------------------
# Build roster tables
# ----------------------------
starters = lineup_state[lineup_state["player_pos"] == "starter"]
bench = lineup_state[lineup_state["player_pos"] == "bench"]

# Order starters by position
starter_rows = []
for pos, slots in roster_template.items():
    pos_players = starters[starters["Pos."] == pos].head(slots)
    starter_rows.append(pos_players)

starters = pd.concat(starter_rows) if starter_rows else pd.DataFrame()

# ----------------------------
# Display roster
# ----------------------------
st.subheader(f"{selected_team}'s Lineup")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Starters")
    if starters.empty:
        st.info("No starters set.")
    else:
        st.dataframe(
            starters[["player_name", "Pos.", "team"]],
            hide_index=True,
            use_container_width=True
        )

with col2:
    st.markdown("### Bench")
    if bench.empty:
        st.info("No bench players.")
    else:
        st.dataframe(
            bench[["player_name", "Pos.", "team"]],
            hide_index=True,
            use_container_width=True
        )

# ----------------------------
# Swap Players
# ----------------------------
st.divider()
st.subheader("🔄 Swap Players (Starter ↔ Bench)")

if starters.empty or bench.empty:
    st.info("You need at least one starter and one bench player to swap.")
    st.stop()

# Session state
if "swap_out" not in st.session_state:
    st.session_state.swap_out = ""
if "swap_in" not in st.session_state:
    st.session_state.swap_in = ""

swap_out_options = [""] + starters["player_name"].tolist()
swap_out = st.selectbox(
    "Select starter to swap out",
    swap_out_options,
    index=swap_out_options.index(st.session_state.swap_out)
    if st.session_state.swap_out in swap_out_options else 0
)

st.session_state.swap_out = swap_out

# Bench filtered by position
if swap_out:
    out_pos = starters.loc[
        starters["player_name"] == swap_out, "Pos."
    ].values[0]
    bench_candidates = bench[bench["Pos."] == out_pos]["player_name"].tolist()
else:
    bench_candidates = []

swap_in_options = [""] + bench_candidates
swap_in = st.selectbox(
    "Select bench player to swap in",
    swap_in_options,
    index=swap_in_options.index(st.session_state.swap_in)
    if st.session_state.swap_in in swap_in_options else 0
)

st.session_state.swap_in = swap_in

# ----------------------------
# Execute swap
# ----------------------------
if st.button("Swap Players") and swap_out and swap_in:

    db_utils.swap_lineup_state(
        team_name=selected_team,
        player_out=swap_out,
        player_in=swap_in
    )

    st.success("✅ Players swapped successfully!")

    # Reset state
    st.session_state.swap_out = ""
    st.session_state.swap_in = ""

    # Force reload
    st.experimental_rerun()
