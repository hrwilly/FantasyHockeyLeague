import streamlit as st
import pandas as pd
import db_utils

st.title("🔁 Trade Center")

# -----------------------------
# Load core data
# -----------------------------
teams_df = db_utils.load_teams()
players_df = db_utils.load_players()

if teams_df.empty:
    st.warning("No teams found.")
    st.stop()

team_names = teams_df["team_name"].tolist()

# Prefer whatever the user picked on My Team page
default_my_team = st.session_state.get("team_name", team_names[0])

# -----------------------------
# Helpers
# -----------------------------
def roster_df_for_team(team_name: str) -> pd.DataFrame:
    r = players_df[players_df["held_by"] == team_name].copy()
    if r.empty:
        return r
    # Keep it simple for trading
    cols = [c for c in ["Name", "Pos.", "team"] if c in r.columns]
    r = r[cols].sort_values(["Pos.", "Name"]).reset_index(drop=True)
    return r

def selectable_editor(df: pd.DataFrame, key: str, label: str, checkbox_label: str) -> list[dict]:
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
    # Return [{"Name":..., "team":...}, ...] for db_utils
    out = chosen[["Name", "team"]].to_dict(orient="records")
    return out

def render_trade_items(items_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (proposer_sends, recipient_sends) views."""
    if items_df.empty:
        return items_df, items_df
    # Group by from_team
    return (
        items_df[["from_team", "to_team", "player_name", "player_team"]],
        items_df[["from_team", "to_team", "player_name", "player_team"]],
    )

# -----------------------------
# Propose a trade
# -----------------------------
st.subheader("📨 Propose a Trade")

colA, colB = st.columns(2)
with colA:
    my_team = st.selectbox("Your team", team_names, index=team_names.index(default_my_team))
with colB:
    partner_choices = [t for t in team_names if t != my_team]
    partner_team = st.selectbox("Trade partner", partner_choices)

left, right = st.columns(2)

with left:
    my_roster = roster_df_for_team(my_team)
    give_players = selectable_editor(
        my_roster,
        key="give_editor",
        label=f"{my_team} roster (who you SEND)",
        checkbox_label="Send",
    )

with right:
    partner_roster = roster_df_for_team(partner_team)
    receive_players = selectable_editor(
        partner_roster,
        key="receive_editor",
        label=f"{partner_team} roster (who you RECEIVE)",
        checkbox_label="Receive",
    )

message = st.text_input("Message (optional)", placeholder="e.g., Need a goalie — willing to move a top forward")

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
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

with col2:
    if st.button("🧹 Clear selections"):
        # Clear editors
        for k in ["give_editor", "receive_editor"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

st.divider()

# -----------------------------
# Trade Inbox / Outbox
# -----------------------------
st.subheader("📬 Trades")

viewer_team = st.selectbox("View trades for team", team_names, index=team_names.index(my_team))
trades = db_utils.load_trades_for_team(viewer_team)

if trades.empty:
    st.info("No trades yet.")
    st.stop()

# Pretty columns
show_cols = ["created_at", "proposer_team", "recipient_team", "status", "message", "id", "parent_trade_id"]
for c in show_cols:
    if c not in trades.columns:
        trades[c] = None

tab_inbox, tab_outbox, tab_all = st.tabs(["📥 Inbox", "📤 Outbox", "🗂️ All"])

def trade_list(df: pd.DataFrame, title: str):
    st.markdown(f"#### {title}")
    if df.empty:
        st.info("None.")
        return

    # show newest first
    df = df.sort_values("created_at", ascending=False)

    for _, t in df.iterrows():
        trade_id = t["id"]
        status = t["status"]
        proposer = t["proposer_team"]
        recipient = t["recipient_team"]
        created_at = str(t["created_at"])[:19].replace("T", " ")
        msg = t.get("message") or ""

        with st.expander(f"{created_at} — {proposer} ➜ {recipient}  |  {status}"):
            if msg:
                st.caption(msg)

            items = db_utils.load_trade_players(trade_id)
            if items.empty:
                st.warning("No players on this trade.")
            else:
                left_c, right_c = st.columns(2)

                with left_c:
                    st.markdown(f"**{proposer} sends**")
                    st.dataframe(
                        items[items["from_team"] == proposer][["player_name", "player_team"]],
                        hide_index=True,
                        use_container_width=True,
                    )

                with right_c:
                    st.markdown(f"**{recipient} sends**")
                    st.dataframe(
                        items[items["from_team"] == recipient][["player_name", "player_team"]],
                        hide_index=True,
                        use_container_width=True,
                    )

            # Actions
            is_recipient_viewing = (viewer_team == recipient)
            is_proposer_viewing = (viewer_team == proposer)

            action_row = st.columns(4)

            # Accept/Decline only if recipient and still proposed
            if is_recipient_viewing and status == "PROPOSED":
                if action_row[0].button("✅ Accept", key=f"acc_{trade_id}"):
                    try:
                        db_utils.execute_trade(trade_id)
                        db_utils.set_trade_status(trade_id, "ACCEPTED", actor_team=viewer_team)
                        st.success("Trade accepted and executed.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

                if action_row[1].button("❌ Decline", key=f"dec_{trade_id}"):
                    db_utils.set_trade_status(trade_id, "DECLINED", actor_team=viewer_team)
                    st.success("Trade declined.")
                    st.rerun()

                # Counter
                if action_row[2].button("🔁 Counter", key=f"ctr_btn_{trade_id}"):
                    st.session_state["countering_trade_id"] = trade_id
                    st.rerun()

            # Cancel only if proposer and still proposed
            if is_proposer_viewing and status == "PROPOSED":
                if action_row[3].button("🛑 Cancel", key=f"can_{trade_id}"):
                    db_utils.set_trade_status(trade_id, "CANCELLED", actor_team=viewer_team)
                    st.success("Trade cancelled.")
                    st.rerun()

            # Counter UI
            if st.session_state.get("countering_trade_id") == trade_id:
                st.markdown("---")
                st.markdown("### Build Counter Offer")

                # For a counter: new proposer is the viewer (recipient), new recipient is original proposer
                new_proposer = viewer_team
                new_recipient = proposer

                cc1, cc2 = st.columns(2)
                with cc1:
                    give = selectable_editor(
                        roster_df_for_team(new_proposer),
                        key=f"ctr_give_{trade_id}",
                        label=f"{new_proposer} roster (you SEND)",
                        checkbox_label="Send",
                    )
                with cc2:
                    recv = selectable_editor(
                        roster_df_for_team(new_recipient),
                        key=f"ctr_recv_{trade_id}",
                        label=f"{new_recipient} roster (you RECEIVE)",
                        checkbox_label="Receive",
                    )

                ctr_msg = st.text_input("Counter message (optional)", key=f"ctr_msg_{trade_id}")

                b1, b2 = st.columns(2)
                with b1:
                    if st.button("📨 Submit Counter", key=f"ctr_submit_{trade_id}", disabled=(len(give)+len(recv) == 0)):
                        new_id = db_utils.counter_trade(
                            old_trade_id=trade_id,
                            actor_team=viewer_team,
                            proposer_team=new_proposer,
                            recipient_team=new_recipient,
                            give_players=give,
                            receive_players=recv,
                            message=ctr_msg or None,
                        )
                        st.success(f"Counter sent! (id={new_id})")
                        st.session_state.pop("countering_trade_id", None)
                        st.rerun()
                with b2:
                    if st.button("Nevermind", key=f"ctr_cancel_{trade_id}"):
                        st.session_state.pop("cou_
