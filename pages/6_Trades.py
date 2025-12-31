import streamlit as st
import pandas as pd
import db_utils

st.set_page_config(page_title="Trade Center", page_icon="🔁", layout="wide")
st.title("🔁 Trade Center")

# -----------------------------
# Load core data
# -----------------------------
teams_df = db_utils.load_teams()
players_df = db_utils.load_players()
points_df = db_utils.load_points()
stats_df = db_utils.load_last_week_stats()

if teams_df.empty:
    st.warning("No teams found.")
    st.stop()

team_names = teams_df["team_name"].tolist()
default_my_team = st.session_state.get("team_name", team_names[0])

# -----------------------------
# Enrich players with last_week_stats + WeeklyPts + CumulativePts
# -----------------------------
players = players_df.copy()

# Merge last_week_stats (all columns from last_week_stats come along)
if not stats_df.empty:
    players = pd.merge(players, stats_df, on=["Name", "team"], how="left")

# WeeklyPts + CumulativePts (same idea you used elsewhere)
if not points_df.empty and "Week" in points_df.columns:
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

# -----------------------------
# Helpers
# -----------------------------
def roster_df_for_team(team_name: str) -> pd.DataFrame:
    r = players[players["held_by"] == team_name].copy()
    if r.empty:
        return r

    # Display EVERYTHING except held_by (since that's just internal ownership)
    if "held_by" in r.columns:
        r = r.drop(columns=["held_by"])

    # Prefer stable sorting if Pos. exists
    sort_cols = [c for c in ["Pos.", "Name"] if c in r.columns]
    if sort_cols:
        r = r.sort_values(sort_cols)

    return r.reset_index(drop=True)


def selectable_editor(df: pd.DataFrame, key: str, label: str, checkbox_label: str):
    st.markdown(f"### {label}")
    if df.empty:
        st.info("No players.")
        return []

    ed = df.copy()
    ed.insert(0, checkbox_label, False)

    edited = st.data_editor(
        ed,
        hide_index=True,
        key=key,
        disabled=[c for c in ed.columns if c != checkbox_label],
        use_container_width=True,
        height=420,
    )

    chosen = edited[edited[checkbox_label] == True]
    if chosen.empty:
        return []

    # db_utils expects [{"Name":..., "team":...}, ...]
    # Make sure these columns exist
    if "Name" not in chosen.columns or "team" not in chosen.columns:
        st.error("Roster table must include Name and team columns.")
        return []

    return chosen[["Name", "team"]].to_dict(orient="records")


def trade_items_with_player_columns(items: pd.DataFrame) -> pd.DataFrame:
    """
    Takes trade_players rows and merges on current player data so you show:
    all last_week_stats columns + WeeklyPts + CumulativePts + whatever is in players.
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

    # If for some reason meta match fails, keep the trade text fields
    merged["Name"] = merged["Name"].fillna(merged["player_name"])
    merged["team"] = merged["team"].fillna(merged["player_team"])

    # Remove redundant columns
    merged = merged.drop(columns=["player_name", "player_team"], errors="ignore")

    # Put Name/team near the front
    front = [c for c in ["Name", "team", "Pos.", "WeeklyPts", "CumulativePts"] if c in merged.columns]
    rest = [c for c in merged.columns if c not in front]
    merged = merged[front + rest]

    # Nice sort if possible
    sort_cols = [c for c in ["Pos.", "Name"] if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols)

    return merged.reset_index(drop=True)


# -----------------------------
# Propose a trade
# -----------------------------
st.subheader("📨 Propose a Trade")

c1, c2 = st.columns(2)
with c1:
    my_team = st.selectbox("Your team", team_names, index=team_names.index(default_my_team))
with c2:
    partner_choices = [t for t in team_names if t != my_team]
    partner_team = st.selectbox("Trade partner", partner_choices)

# STACKED roster selectors (top then bottom)
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
        st.rerun()

with b2:
    if st.button("🧹 Clear selections"):
        for k in ["give_editor", "receive_editor"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

st.divider()

# -----------------------------
# Trade list
# -----------------------------
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

            # STACKED trade detail (top then bottom), showing full columns
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

        if is_recipient_viewing and status == "PROPOSED":
            if a1.button("✅ Accept", key="acc_" + trade_id):
                try:
                    db_utils.execute_trade(trade_id)
                    db_utils.set_trade_status(trade_id, "ACCEPTED", actor_team=viewer_team)
                    st.success("Trade accepted and executed.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if a2.button("❌ Decline", key="dec_" + trade_id):
                db_utils.set_trade_status(trade_id, "DECLINED", actor_team=viewer_team)
                st.success("Trade declined.")
                st.rerun()

            if a3.button("🔁 Counter", key="ctr_" + trade_id):
                st.session_state["counter_trade_id"] = trade_id
                st.rerun()

        if is_proposer_viewing and status == "PROPOSED":
            if a3.button("🛑 Cancel", key="can_" + trade_id):
                db_utils.set_trade_status(trade_id, "CANCELLED", actor_team=viewer_team)
                st.success("Trade cancelled.")
                st.rerun()

        # Counter UI (also stacked)
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
                st.rerun()

            if s2.button("Nevermind", key="ctr_cancel_" + trade_id):
                st.session_state.pop("counter_trade_id", None)
                st.rerun()
