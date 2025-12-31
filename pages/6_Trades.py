# pages/6_Trades.py

import streamlit as st
import pandas as pd
import db_utils

st.set_page_config(page_title="Trade Center", page_icon="🔁", layout="wide")
st.title("🔁 Trade Center")

# ======================================================
# CACHED DATA LOADER (BIG SPEED WIN)
# ======================================================
@st.cache_data(ttl=120, show_spinner=False)
def load_trade_center_data():
    teams_df = db_utils.load_teams()
    players_df = db_utils.load_players()
    points_df = db_utils.load_points()
    stats_df = db_utils.load_last_week_stats()

    players = players_df.copy()

    # Merge last_week_stats (all columns)
    if stats_df is not None and not stats_df.empty:
        players = pd.merge(players, stats_df, on=["Name", "team"], how="left")

    # WeeklyPts + CumulativePts (based on latest week in points table)
    if points_df is not None and not points_df.empty and "Week" in points_df.columns:
        latest_week = points_df["Week"].max()

        weekly = points_df[points_df["Week"] == latest_week][["Name", "team", "FantasyPoints"]].copy()
        weekly_total = weekly.groupby(["Name", "team"], as_index=False)["FantasyPoints"].sum()
        weekly_total.rename(columns={"FantasyPoints": "WeeklyPts"}, inplace=True)

        cumulative = points_df.groupby(["Name", "team"], as_index=False)["FantasyPoints"].sum()
        cumulative.rename(columns={"FantasyPoints": "CumulativePts"}, inplace=True)

        players = pd.merge(players, weekly_total, on=["Name", "team"], how="left")
        players = pd.merge(players, cumulative, on=["Name", "team"], how="left")

    # Fill missing point totals with 0
    for c in ["WeeklyPts", "CumulativePts"]:
        if c in players.columns:
            players[c] = pd.to_numeric(players[c], errors="coerce").fillna(0)

    return teams_df, players


# ======================================================
# LOAD DATA
# ======================================================
teams_df, players = load_trade_center_data()

if teams_df.empty:
    st.warning("No teams found.")
    st.stop()

team_names = teams_df["team_name"].tolist()
default_my_team = st.session_state.get("team_name", team_names[0])


# ======================================================
# HELPERS
# ======================================================
def roster_df_for_team(team_name: str) -> pd.DataFrame:
    r = players[players["held_by"] == team_name].copy()
    if r.empty:
        return r

    # Display everything except held_by (ownership field)
    if "held_by" in r.columns:
        r = r.drop(columns=["held_by"])

    sort_cols = [c for c in ["Pos.", "Name"] if c in r.columns]
    if sort_cols:
        r = r.sort_values(sort_cols)

    return r.reset_index(drop=True)


def selectable_editor(df: pd.DataFrame, key: str, label: str, checkbox_label: str):
    """
    FAST UI:
      - data_editor shows a compact selection view
      - expander shows the full roster with ALL columns (last_week_stats + WeeklyPts + CumulativePts)
    """
    st.markdown(f"### {label}")
    if df.empty:
        st.info("No players.")
        return []

    # Compact columns for selection (fast to render)
    preferred = [c for c in ["Name", "Pos.", "team", "WeeklyPts", "CumulativePts"] if c in df.columns]
    if preferred:
        compact = df[preferred].copy()
    else:
        # Minimum required columns
        compact = df[[c for c in ["Name", "team"] if c in df.columns]].copy()

    ed = compact.copy()
    ed.insert(0, checkbox_label, False)

    edited = st.data_editor(
        ed,
        hide_index=True,
        key=key,
        disabled=[c for c in ed.columns if c != checkbox_label],
        use_container_width=True,
        height=380,
    )

    # Full roster view (ALL columns)
    with st.expander("Show full stats columns"):
        st.dataframe(df, hide_index=True, use_container_width=True)

    chosen = edited[edited[checkbox_label] == True]
    if chosen.empty:
        return []

    # Ensure required columns exist
    if "Name" not in chosen.columns or "team" not in chosen.columns:
        st.error("Roster must include Name and team columns.")
        return []

    return chosen[["Name", "team"]].to_dict(orient="records")


def trade_items_with_player_columns(items: pd.DataFrame) -> pd.DataFrame:
    """
    Merge trade line items to current player data so we can show:
    - all last_week_stats columns
    - WeeklyPts + CumulativePts
    - any other columns present in players
    """
    if items.empty:
        return items

    meta = players.copy()
    if "held_by" in meta.columns:
        meta = meta.drop(columns=["held_by"])

    merged = items.merge(
        meta,
        left_on=["player_name", "player_team"],
        right_on=["Name", "team"],
        how="left",
        suffixes=("", "_meta"),
    )

    merged["Name"] = merged["Name"].fillna(merged["player_name"])
    merged["team"] = merged["team"].fillna(merged["player_team"])

    merged = merged.drop(columns=["player_name", "player_team"], errors="ignore")

    # Put core columns near front if they exist
    front = [c for c in ["from_team", "to_team", "Name", "team", "Pos.", "WeeklyPts", "CumulativePts"] if c in merged.columns]
    rest = [c for c in merged.columns if c not in front]
    merged = merged[front + rest]

    sort_cols = [c for c in ["Pos.", "Name"] if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols)

    return merged.reset_index(drop=True)


# ======================================================
# UI: PROPOSE A TRADE
# ======================================================
st.subheader("📨 Propose a Trade")

c1, c2 = st.columns(2)
with c1:
    my_team = st.selectbox("Your team", team_names, index=team_names.index(default_my_team))
with c2:
    partner_choices = [t for t in team_names if t != my_team]
    partner_team = st.selectbox("Trade partner", partner_choices)

# STACKED rosters (top then bottom)
give_players = selectable_editor(
    roster_df_for_team(my_team),
    key="give_editor",
    label=f"{my_team} roster (who you SEND)",
    checkbox_label="Send",
)

st.divider()

receive_players = selectable_editor(
    roster_df_for_team(partner_team),
    key="receive_editor",
    label=f"{partner_team} roster (who you RECEIVE)",
    checkbox_label="Receive",
)

message = st.text_input("Message (optional)", placeholder="e.g., Need a goalie — willing to move a top forward")

b1, b2 = st.columns([1, 1])
with b1:
    can_propose = (len(give_players) + len(receive_players)) > 0
    if st.button("📨 Propose Trade", disabled=not can_propose):
        trade_id = db_utils.create_trade(
            proposer_team=my_team,
            recipient_team=partner_team,
            give_players=give_players,
            receive_players=receive_players,
            message=message or None,
        )
        st.success(f"Trade proposed! (id={trade_id})")
        st.cache_data.clear()
        st.rerun()

with b2:
    if st.button("🧹 Clear selections"):
        for k in ["give_editor", "receive_editor"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

st.divider()


# ======================================================
# UI: VIEW TRADES
# ======================================================
st.subheader("📬 Trades")

viewer_team = st.selectbox("View trades for team", team_names, index=team_names.index(my_team))
trades = db_utils.load_trades_for_team(viewer_team)

if trades.empty:
    st.info("No trades yet.")
    st.stop()

trades = trades.sort_values("created_at", ascending=False)

for _, t in trades.iterrows():
    trade_id = t["id"]
    status = t["status"]
    proposer = t["proposer_team"]
    recipient = t["recipient_team"]
    created_at = str(t["created_at"])[:19].replace("T", " ")
    msg = t.get("message") or ""

    with st.expander(f"{created_at} — {proposer} ➜ {recipient} | {status}"):
        if msg:
            st.caption(msg)

        items = db_utils.load_trade_players(trade_id)

        if items.empty:
            st.warning("No players on this trade.")
        else:
            proposer_sends = items[items["from_team"] == proposer].copy()
            recipient_sends = items[items["from_team"] == recipient].copy()

            # STACKED trade details
            st.markdown(f"### {proposer} sends")
            st.dataframe(
                trade_items_with_player_columns(proposer_sends),
                hide_index=True,
                use_container_width=True,
            )

            st.markdown(f"### {recipient} sends")
            st.dataframe(
                trade_items_with_player_columns(recipient_sends),
                hide_index=True,
                use_container_width=True,
            )

        is_recipient_viewing = (viewer_team == recipient)
        is_proposer_viewing = (viewer_team == proposer)

        a1, a2, a3 = st.columns(3)

        # Recipient actions
        if is_recipient_viewing and status == "PROPOSED":
            if a1.button("✅ Accept", key="acc_" + trade_id):
                try:
                    db_utils.execute_trade(trade_id)
                    db_utils.set_trade_status(trade_id, "ACCEPTED", actor_team=viewer_team)
                    st.success("Trade accepted and executed.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if a2.button("❌ Decline", key="dec_" + trade_id):
                db_utils.set_trade_status(trade_id, "DECLINED", actor_team=viewer_team)
                st.success("Trade declined.")
                st.cache_data.clear()
                st.rerun()

            if a3.button("🔁 Counter", key="ctr_" + trade_id):
                st.session_state["counter_trade_id"] = trade_id
                st.rerun()

        # Proposer actions
        if is_proposer_viewing and status == "PROPOSED":
            if a3.button("🛑 Cancel", key="can_" + trade_id):
                db_utils.set_trade_status(trade_id, "CANCELLED", actor_team=viewer_team)
                st.success("Trade cancelled.")
                st.cache_data.clear()
                st.rerun()

        # Counter UI (stacked)
        if st.session_state.get("counter_trade_id") == trade_id:
            st.markdown("---")
            st.markdown("## Build Counter Offer")

            new_proposer = viewer_team
            new_recipient = proposer

            ctr_give = selectable_editor(
                roster_df_for_team(new_proposer),
                key="ctr_give_" + trade_id,
                label=f"{new_proposer} roster (you SEND)",
                checkbox_label="Send",
            )

            st.divider()

            ctr_recv = selectable_editor(
                roster_df_for_team(new_recipient),
                key="ctr_recv_" + trade_id,
                label=f"{new_recipient} roster (you RECEIVE)",
                checkbox_label="Receive",
            )

            ctr_msg = st.text_input("Counter message (optional)", key="ctr_msg_" + trade_id)

            s1, s2 = st.columns(2)
            if s1.button(
                "📨 Submit Counter",
                key="ctr_submit_" + trade_id,
                disabled=(len(ctr_give) + len(ctr_recv) == 0),
            ):
                new_id = db_utils.counter_trade(
                    old_trade_id=trade_id,
                    actor_team=viewer_team,
                    proposer_team=new_proposer,
                    recipient_team=new_recipient,
                    give_players=ctr_give,
                    receive_players=ctr_recv,
                    message=ctr_msg or None,
                )
                st.success(f"Counter sent! (id={new_id})")
                st.session_state.pop("counter_trade_id", None)
                st.cache_data.clear()
                st.rerun()

            if s2.button("Nevermind", key="ctr_cancel_" + trade_id):
                st.session_state.pop("counter_trade_id", None)
                st.rerun()

def _pos_group(pos_val: str) -> str:
    """
    Normalize player positions into groups for lineup integrity.
    Adjust if your Pos. values differ.
    """
    if not pos_val:
        return "F"
    p = str(pos_val).upper()
    if "G" in p:
        return "G"
    if "D" in p:
        return "D"
    return "F"


def _get_lineup_shape(team_name: str):
    """
    Returns (starter_total, starters_by_group) based on CURRENT lineup_state.
    """
    rows = supabase.table("lineup_state").select("*").eq("team_name", team_name).execute().data or []
    starter_rows = [r for r in rows if r.get("player_pos") == "starter"]

    starter_total = len(starter_rows)
    starters_by_group = {}
    for r in starter_rows:
        g = _pos_group(r.get("Pos."))
        starters_by_group[g] = starters_by_group.get(g, 0) + 1

    return starter_total, starters_by_group


def _fetch_roster_for_team(team_name: str):
    """
    Fetch current roster from players table. Must include Name, team, Pos.
    Uses select('*') to avoid the Pos. select parsing issue.
    """
    roster = supabase.table("players").select("*").eq("held_by", team_name).execute().data or []
    # normalize expected fields
    out = []
    for r in roster:
        out.append({
            "Name": r.get("Name"),
            "team": r.get("team"),
            "Pos.": r.get("Pos."),
        })
    # remove any weird nulls
    out = [r for r in out if r["Name"] and r["team"]]
    return out


def _rebuild_lineup_state_to_shape(team_name: str, starter_total: int, starters_by_group: dict):
    """
    Rebuild lineup_state for team_name so starters match starter_total and starters_by_group.
    Keeps existing starters where possible.
    """
    # Current lineup_state (for "keep starters" preference)
    current = supabase.table("lineup_state").select("*").eq("team_name", team_name).execute().data or []
    current_pos_by_name = {r["player_name"]: r.get("player_pos", "bench") for r in current if r.get("player_name")}

    # Current roster after trade
    roster = _fetch_roster_for_team(team_name)
    if not roster:
        # If team somehow has no players, clear lineup_state
        supabase.table("lineup_state").delete().eq("team_name", team_name).execute()
        return

    # Build pools by group
    by_group = {"F": [], "D": [], "G": []}
    for p in roster:
        g = _pos_group(p.get("Pos."))
        by_group.setdefault(g, []).append(p)

    # Prefer to keep people who were already starters
    for g in by_group:
        by_group[g].sort(key=lambda x: (current_pos_by_name.get(x["Name"]) != "starter", x["Name"]))

    # Pick starters per group to match previous shape
    starters = []
    remaining = set((p["Name"], p["team"]) for p in roster)

    for g, need in starters_by_group.items():
        pool = by_group.get(g, [])
        take = pool[: max(0, int(need))]
        for p in take:
            starters.append(p)
            remaining.discard((p["Name"], p["team"]))

    # If we still need more starters (e.g., shape didn’t cover all starter slots),
    # fill with best available (prefer existing starters; else alphabetical).
    if len(starters) < starter_total:
        remaining_list = [p for p in roster if (p["Name"], p["team"]) in remaining]
        remaining_list.sort(key=lambda x: (current_pos_by_name.get(x["Name"]) != "starter", x["Name"]))
        needed = starter_total - len(starters)
        starters.extend(remaining_list[:needed])
        for p in remaining_list[:needed]:
            remaining.discard((p["Name"], p["team"]))

    starter_set = set((p["Name"], p["team"]) for p in starters)

    # Rebuild ALL rows (simple + consistent). This guarantees Pos. and team are correct.
    new_rows = []
    for p in roster:
        is_starter = (p["Name"], p["team"]) in starter_set
        new_rows.append({
            "team_name": team_name,
            "player_name": p["Name"],
            "player_pos": "starter" if is_starter else "bench",
            "Pos.": p.get("Pos."),
            "team": p.get("team"),
        })

    # Replace lineup_state for this team (safe if lineup_state only stores lineup info)
    supabase.table("lineup_state").delete().eq("team_name", team_name).execute()
    supabase.table("lineup_state").insert(new_rows).execute()


def execute_trade(trade_id: str):
    """
    Execute trade and keep lineup_state integrity:
      - preserve each team's starter counts + starter-by-group counts from before trade
      - rebuild lineup_state after ownership changes
    """
    trade = supabase.table("trades").select("*").eq("id", trade_id).execute().data[0]
    if trade["status"] != "PROPOSED":
        raise ValueError(f"Trade is not PROPOSED (status={trade['status']}).")

    items = load_trade_players(trade_id)
    if items.empty:
        raise ValueError("Trade has no players.")

    team_a = trade["proposer_team"]
    team_b = trade["recipient_team"]

    # 1) Snapshot lineup shapes BEFORE trade
    a_starter_total, a_by_group = _get_lineup_shape(team_a)
    b_starter_total, b_by_group = _get_lineup_shape(team_b)

    # 2) Verify ownership
    problems = []
    for _, row in items.iterrows():
        name = row["player_name"]
        pteam = row["player_team"]
        from_team = row["from_team"]

        current = (
            supabase.table("players")
            .select("Name, team, held_by")
            .eq("Name", name)
            .eq("team", pteam)
            .execute()
            .data
        )
        if not current:
            problems.append(f"{name} ({pteam}) not found in players table.")
            continue
        if current[0].get("held_by") != from_team:
            problems.append(
                f"{name} ({pteam}) expected held_by={from_team}, but is held_by={current[0].get('held_by')}"
            )

    if problems:
        raise ValueError("Cannot execute trade:\n- " + "\n- ".join(problems))

    # 3) Apply ownership swaps
    for _, row in items.iterrows():
        supabase.table("players").update(
            {"held_by": row["to_team"]}
        ).eq("Name", row["player_name"]).eq("team", row["player_team"]).execute()

    # 4) Rebuild lineup_state for both teams to match their prior shapes
    _rebuild_lineup_state_to_shape(team_a, a_starter_total, a_by_group)
    _rebuild_lineup_state_to_shape(team_b, b_starter_total, b_by_group)
