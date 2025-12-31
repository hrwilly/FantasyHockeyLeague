# pages/6_Trades.py

import streamlit as st
import pandas as pd
import db_utils

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(page_title="Trade Center", page_icon="🔁", layout="wide")
st.title("🔁 Trade Center")

ROSTER_TOTAL = 17  # 6F + 4D + 2G starters + 5 bench = 17 total

# session flags for accept/finalize
if "pending_accept_trade_id" not in st.session_state:
    st.session_state["pending_accept_trade_id"] = None

# ======================================================
# CACHED DATA LOADER (FAST)
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

    for c in ["WeeklyPts", "CumulativePts"]:
        if c in players.columns:
            players[c] = pd.to_numeric(players[c], errors="coerce").fillna(0)

    return teams_df, players


teams_df, players = load_trade_center_data()

if teams_df.empty:
    st.warning("No teams found.")
    st.stop()

team_names = teams_df["team_name"].tolist()
default_my_team = st.session_state.get("team_name", team_names[0])


# ======================================================
# HELPERS
# ======================================================
def strip_internal_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "held_by" in out.columns:
        out = out.drop(columns=["held_by"])
    return out


def roster_df_for_team(team_name: str) -> pd.DataFrame:
    r = players[players["held_by"] == team_name].copy()
    if r.empty:
        return r
    r = strip_internal_cols(r)

    # Stable sort if available
    sort_cols = [c for c in ["Pos.", "Name"] if c in r.columns]
    if sort_cols:
        r = r.sort_values(sort_cols)

    return r.reset_index(drop=True)


def post_trade_roster_df(team_name: str, items_df: pd.DataFrame) -> pd.DataFrame:
    """
    Simulate roster AFTER the trade swaps (but BEFORE balancing drops/pickups).
    Uses the current 'players' dataframe (pre-trade) and trade items to build a post-trade roster.
    """
    current = players[players["held_by"] == team_name].copy()

    # remove outgoing
    outgoing = items_df[items_df["from_team"] == team_name][["player_name", "player_team"]].copy()
    if not outgoing.empty:
        outgoing_keys = set(zip(outgoing["player_name"], outgoing["player_team"]))
        current = current[~list(zip(current["Name"], current["team"])).__iter__()]  # placeholder to satisfy linter

    # The above line isn't valid logic; do it safely:
    if not outgoing.empty:
        current["_key"] = list(zip(current["Name"], current["team"]))
        outgoing_keys = set(zip(outgoing["player_name"], outgoing["player_team"]))
        current = current[~current["_key"].isin(outgoing_keys)].drop(columns=["_key"])

    # add incoming
    incoming = items_df[items_df["to_team"] == team_name][["player_name", "player_team"]].copy()
    if not incoming.empty:
        inc_keys = set(zip(incoming["player_name"], incoming["player_team"]))
        inc_rows = players[list(zip(players["Name"], players["team"])) if False else players.index]  # placeholder

    if not incoming.empty:
        players_tmp = players.copy()
        players_tmp["_key"] = list(zip(players_tmp["Name"], players_tmp["team"]))
        inc_keys = set(zip(incoming["player_name"], incoming["player_team"]))
        inc_rows = players_tmp[players_tmp["_key"].isin(inc_keys)].drop(columns=["_key"])
        current = pd.concat([current, inc_rows], ignore_index=True)

    # de-dupe
    current = current.drop_duplicates(subset=["Name", "team"], keep="first")
    current = strip_internal_cols(current)

    sort_cols = [c for c in ["Pos.", "Name"] if c in current.columns]
    if sort_cols:
        current = current.sort_values(sort_cols)

    return current.reset_index(drop=True)


def required_drops_and_open_slots(team_name: str, items_df: pd.DataFrame) -> tuple[int, int, int]:
    """
    Returns (post_count, required_drops, open_slots)
    post_count is roster size after trade but before balancing.
    """
    current_count = int((players["held_by"] == team_name).sum())
    incoming = int((items_df["to_team"] == team_name).sum())
    outgoing = int((items_df["from_team"] == team_name).sum())
    post_count = current_count + incoming - outgoing

    required_drops = max(0, post_count - ROSTER_TOTAL)
    open_slots = max(0, ROSTER_TOTAL - post_count)
    return post_count, required_drops, open_slots


def pick_from_editor(df: pd.DataFrame, key: str, checkbox_label: str = "Pick"):
    """
    Returns list of {"Name": ..., "team": ...} from checked rows.
    Uses a compact editor for speed + full table in an expander.
    """
    if df is None or df.empty:
        st.info("No players.")
        return []

    preferred = [c for c in ["Name", "Pos.", "team", "WeeklyPts", "CumulativePts"] if c in df.columns]
    compact = df[preferred].copy() if preferred else df[["Name", "team"]].copy()

    ed = compact.copy()
    ed.insert(0, checkbox_label, False)

    edited = st.data_editor(
        ed,
        hide_index=True,
        key=key,
        disabled=[c for c in ed.columns if c != checkbox_label],
        use_container_width=True,
        height=360,
    )

    with st.expander("Show full columns"):
        st.dataframe(df, hide_index=True, use_container_width=True)

    chosen = edited[edited[checkbox_label] == True]
    if chosen.empty:
        return []

    return chosen[["Name", "team"]].to_dict(orient="records")


def trade_items_with_player_columns(items: pd.DataFrame) -> pd.DataFrame:
    """
    Merge trade line items to current player data for rich display.
    """
    if items.empty:
        return items

    meta = strip_internal_cols(players)

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

    front = [c for c in ["from_team", "to_team", "Name", "team", "Pos.", "WeeklyPts", "CumulativePts"] if c in merged.columns]
    rest = [c for c in merged.columns if c not in front]
    merged = merged[front + rest]

    sort_cols = [c for c in ["Pos.", "Name"] if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols)

    return merged.reset_index(drop=True)


# ======================================================
# UI: PROPOSE A TRADE (STACKED)
# ======================================================
st.subheader("📨 Propose a Trade")

c1, c2 = st.columns(2)
with c1:
    my_team = st.selectbox("Your team", team_names, index=team_names.index(default_my_team))
with c2:
    partner_choices = [t for t in team_names if t != my_team]
    partner_team = st.selectbox("Trade partner", partner_choices)

st.markdown(f"### {my_team} roster (who you SEND)")
give_players = pick_from_editor(
    roster_df_for_team(my_team),
    key="give_editor",
    checkbox_label="Send",
)

st.divider()

st.markdown(f"### {partner_team} roster (who you RECEIVE)")
receive_players = pick_from_editor(
    roster_df_for_team(partner_team),
    key="receive_editor",
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
            st.session_state.pop(k, None)
        st.rerun()

st.divider()


# ======================================================
# UI: TRADES LIST + ACCEPT/DECLINE/COUNTER + FINALIZE
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

            st.markdown(f"### {proposer} sends")
            st.dataframe(trade_items_with_player_columns(proposer_sends), hide_index=True, use_container_width=True)

            st.markdown(f"### {recipient} sends")
            st.dataframe(trade_items_with_player_columns(recipient_sends), hide_index=True, use_container_width=True)

        is_recipient_viewing = (viewer_team == recipient)
        is_proposer_viewing = (viewer_team == proposer)

        a1, a2, a3 = st.columns(3)

        # Recipient actions (PROPOSED only)
        if is_recipient_viewing and status == "PROPOSED":
            if a1.button("✅ Accept", key="acc_" + trade_id):
                st.session_state["pending_accept_trade_id"] = trade_id
                st.rerun()

            if a2.button("❌ Decline", key="dec_" + trade_id):
                db_utils.set_trade_status(trade_id, "DECLINED", actor_team=viewer_team)
                st.success("Trade declined.")
                st.cache_data.clear()
                st.rerun()

            if a3.button("🔁 Counter", key="ctr_" + trade_id):
                st.session_state["counter_trade_id"] = trade_id
                st.rerun()

        # Proposer actions (PROPOSED only)
        if is_proposer_viewing and status == "PROPOSED":
            if a3.button("🛑 Cancel", key="can_" + trade_id):
                db_utils.set_trade_status(trade_id, "CANCELLED", actor_team=viewer_team)
                st.success("Trade cancelled.")
                st.cache_data.clear()
                st.rerun()

        # ------------------------------------------------------
        # FINALIZE ACCEPT (roster balancing) — only for recipient
        # ------------------------------------------------------
        if is_recipient_viewing and status == "PROPOSED" and st.session_state.get("pending_accept_trade_id") == trade_id:
            st.markdown("---")
            st.subheader("Finalize Trade (Roster Balancing)")

            if items.empty:
                st.warning("Cannot finalize: trade has no items.")
            else:
                # compute needed drops/open slots for BOTH teams
                post_count_a, req_drops_a, open_slots_a = required_drops_and_open_slots(proposer, items)
                post_count_b, req_drops_b, open_slots_b = required_drops_and_open_slots(recipient, items)

                st.write(f"Roster rules: **17 total** (6F / 4D / 2G starters + 5 bench).")

                # build post-trade rosters for drop selection
                post_roster_a = post_trade_roster_df(proposer, items)
                post_roster_b = post_trade_roster_df(recipient, items)

                # free agents for optional pickups
                free_agents = players[players["held_by"].isna()].copy()
                free_agents = strip_internal_cols(free_agents)
                # keep it reasonable for UI speed
                free_agents = free_agents.drop_duplicates(subset=["Name", "team"]).head(250).reset_index(drop=True)

                st.markdown(f"### {proposer} (post-trade count: {post_count_a})")
                st.write(f"Required drops: **{req_drops_a}**  |  Optional pickups: **up to {open_slots_a}**")

                drops_a = []
                picks_a = []
                if req_drops_a > 0:
                    st.info("Select exactly the required number of drops. You *may* drop a newly acquired player.")
                    drops_a = pick_from_editor(post_roster_a, key=f"drops_{trade_id}_{proposer}", checkbox_label="Drop")
                if open_slots_a > 0:
                    with st.expander("Optional: pick up free agents now"):
                        picks_a = pick_from_editor(free_agents, key=f"picks_{trade_id}_{proposer}", checkbox_label="Pick up")

                st.divider()

                st.markdown(f"### {recipient} (post-trade count: {post_count_b})")
                st.write(f"Required drops: **{req_drops_b}**  |  Optional pickups: **up to {open_slots_b}**")

                drops_b = []
                picks_b = []
                if req_drops_b > 0:
                    st.info("Select exactly the required number of drops. You *may* drop a newly acquired player.")
                    drops_b = pick_from_editor(post_roster_b, key=f"drops_{trade_id}_{recipient}", checkbox_label="Drop")
                if open_slots_b > 0:
                    with st.expander("Optional: pick up free agents now"):
                        picks_b = pick_from_editor(free_agents, key=f"picks_{trade_id}_{recipient}", checkbox_label="Pick up")

                # enforce limits client-side (backend validates too)
                errs = []
                if len(drops_a) != req_drops_a:
                    errs.append(f"{proposer}: select exactly {req_drops_a} drop(s).")
                if len(drops_b) != req_drops_b:
                    errs.append(f"{recipient}: select exactly {req_drops_b} drop(s).")
                if len(picks_a) > open_slots_a:
                    errs.append(f"{proposer}: pick up at most {open_slots_a}.")
                if len(picks_b) > open_slots_b:
                    errs.append(f"{recipient}: pick up at most {open_slots_b}.")

                if errs:
                    st.warning("Finalize requirements:\n- " + "\n- ".join(errs))

                f1, f2 = st.columns(2)
                with f1:
                    if st.button("✅ Finalize Trade", key="finalize_" + trade_id, disabled=bool(errs)):
                        try:
                            db_utils.execute_trade_balanced(
                                trade_id,
                                drops_by_team={proposer: drops_a, recipient: drops_b},
                                pickups_by_team={proposer: picks_a, recipient: picks_b},
                            )
                            db_utils.set_trade_status(trade_id, "ACCEPTED", actor_team=viewer_team)

                            # Clear cached UI state so Team page updates immediately
                            for k in ["players", "lineup_state", "roster", "starters", "bench"]:
                                st.session_state.pop(k, None)
                            st.session_state["pending_accept_trade_id"] = None
                            st.cache_data.clear()

                            st.success("Trade accepted and finalized.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                with f2:
                    if st.button("Cancel finalize", key="cancel_finalize_" + trade_id):
                        st.session_state["pending_accept_trade_id"] = None
                        st.rerun()

        # ------------------------------------------------------
        # COUNTER UI (unchanged; no balancing until accept)
        # ------------------------------------------------------
        if st.session_state.get("counter_trade_id") == trade_id:
            st.markdown("---")
            st.subheader("Build Counter Offer")

            new_proposer = viewer_team
            new_recipient = proposer

            st.markdown(f"### {new_proposer} roster (you SEND)")
            ctr_give = pick_from_editor(
                roster_df_for_team(new_proposer),
                key="ctr_give_" + trade_id,
                checkbox_label="Send",
            )

            st.divider()

            st.markdown(f"### {new_recipient} roster (you RECEIVE)")
            ctr_recv = pick_from_editor(
                roster_df_for_team(new_recipient),
                key="ctr_recv_" + trade_id,
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
