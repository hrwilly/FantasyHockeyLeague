# pages/6_Trades.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st
import db_utils  # <-- use your current db_utils

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(page_title="Trade Center", page_icon="🔁", layout="wide")
st.title("🔁 Trade Center")

supabase = db_utils.supabase  # reuse the same client as the rest of your app

# ======================================================
# ROSTER RULES
# ======================================================
STARTERS_BY_GROUP = {"F": 6, "D": 4, "G": 2}
ROSTER_TOTAL = 17
STARTER_TOTAL = sum(STARTERS_BY_GROUP.values())  # 12
BENCH_TOTAL = ROSTER_TOTAL - STARTER_TOTAL       # 5

VALID_STATUSES = [
    "PROPOSED",
    "FINALIZE_RECIPIENT",
    "FINALIZE_PROPOSER",
    "ACCEPTED",
    "DECLINED",
    "CANCELLED",
    "COUNTERED",
]


def utc_iso() -> str:
    return datetime.utcnow().isoformat()


# ======================================================
# CACHED DATA PULLS (via db_utils)
# ======================================================
@st.cache_data(ttl=120, show_spinner=False)
def load_teams_df() -> pd.DataFrame:
    return db_utils.load_teams()


@st.cache_data(ttl=120, show_spinner=False)
def load_players_df() -> pd.DataFrame:
    return db_utils.load_players()


@st.cache_data(ttl=120, show_spinner=False)
def load_points_df() -> pd.DataFrame:
    try:
        return db_utils.load_points()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120, show_spinner=False)
def load_last_week_stats_df() -> pd.DataFrame:
    try:
        return db_utils.load_last_week_stats()
    except Exception:
        return pd.DataFrame()


def build_players_display_df() -> pd.DataFrame:
    """
    players + last_week_stats (all cols) + WeeklyPts/CumulativePts
    """
    players = load_players_df().copy()
    if players.empty:
        return players

    stats = load_last_week_stats_df()
    if not stats.empty and set(["Name", "team"]).issubset(stats.columns) and set(["Name", "team"]).issubset(players.columns):
        players = players.merge(stats, on=["Name", "team"], how="left")

    pts = load_points_df()
    if not pts.empty and "Week" in pts.columns and "FantasyPoints" in pts.columns and set(["Name", "team"]).issubset(pts.columns):
        latest_week = pts["Week"].max()

        weekly = pts[pts["Week"] == latest_week][["Name", "team", "FantasyPoints"]].copy()
        weekly_total = weekly.groupby(["Name", "team"], as_index=False)["FantasyPoints"].sum()
        weekly_total.rename(columns={"FantasyPoints": "WeeklyPts"}, inplace=True)

        cumulative = pts.groupby(["Name", "team"], as_index=False)["FantasyPoints"].sum()
        cumulative.rename(columns={"FantasyPoints": "CumulativePts"}, inplace=True)

        players = players.merge(weekly_total, on=["Name", "team"], how="left")
        players = players.merge(cumulative, on=["Name", "team"], how="left")

    for c in ["WeeklyPts", "CumulativePts"]:
        if c in players.columns:
            players[c] = pd.to_numeric(players[c], errors="coerce").fillna(0)

    # Normalize held_by to avoid missing players due to whitespace/casing issues
    if "held_by" in players.columns:
        players["held_by_norm"] = players["held_by"].fillna("").astype(str).str.strip()
    else:
        players["held_by_norm"] = ""

    return players


# ======================================================
# TRADE TABLE OPERATIONS (self-contained here)
# ======================================================
def get_trade(trade_id: str) -> Dict[str, Any]:
    return supabase.table("trades").select("*").eq("id", trade_id).execute().data[0]


def load_trades_for_team(team_name: str) -> pd.DataFrame:
    resp = (
        supabase
        .table("trades")
        .select("*")
        .or_(f"proposer_team.eq.{team_name},recipient_team.eq.{team_name}")
        .order("created_at", desc=True)
        .execute()
    )
    return pd.DataFrame(resp.data or [])


def load_trade_players(trade_id: str) -> pd.DataFrame:
    resp = supabase.table("trade_players").select("*").eq("trade_id", trade_id).execute()
    return pd.DataFrame(resp.data or [])


def set_trade_status(trade_id: str, status: str, actor_team: str):
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    supabase.table("trades").update(
        {
            "status": status,
            "last_action_by": actor_team,
            "last_action_at": utc_iso(),
            "updated_at": utc_iso(),
        }
    ).eq("id", trade_id).execute()


def _safe_update_trade_finalize_fields(trade_id: str, patch: Dict[str, Any]):
    """
    Needs these columns on trades:
      recipient_moves jsonb, proposer_moves jsonb
      recipient_finalized bool, proposer_finalized bool
    """
    try:
        supabase.table("trades").update(patch).eq("id", trade_id).execute()
    except Exception as e:
        raise RuntimeError(
            "Trades finalize columns missing. Run in Supabase SQL:\n\n"
            "alter table trades\n"
            "  add column if not exists recipient_moves jsonb,\n"
            "  add column if not exists proposer_moves jsonb,\n"
            "  add column if not exists recipient_finalized boolean not null default false,\n"
            "  add column if not exists proposer_finalized boolean not null default false;\n\n"
            f"Original error:\n{e}"
        )


def create_trade(
    proposer_team: str,
    recipient_team: str,
    give_players: List[Dict[str, str]],
    receive_players: List[Dict[str, str]],
    message: str | None = None,
    parent_trade_id: str | None = None,
) -> str:
    trade_row = {
        "proposer_team": proposer_team,
        "recipient_team": recipient_team,
        "status": "PROPOSED",
        "message": message,
        "parent_trade_id": parent_trade_id,
        "last_action_by": proposer_team,
        "last_action_at": utc_iso(),
        "updated_at": utc_iso(),
        "recipient_moves": None,
        "proposer_moves": None,
        "recipient_finalized": False,
        "proposer_finalized": False,
    }
    resp = supabase.table("trades").insert(trade_row).execute()
    trade_id = resp.data[0]["id"]

    items = []
    for p in give_players:
        items.append(
            {
                "trade_id": trade_id,
                "from_team": proposer_team,
                "to_team": recipient_team,
                "player_name": p["Name"],
                "player_team": p["team"],
            }
        )
    for p in receive_players:
        items.append(
            {
                "trade_id": trade_id,
                "from_team": recipient_team,
                "to_team": proposer_team,
                "player_name": p["Name"],
                "player_team": p["team"],
            }
        )

    if items:
        supabase.table("trade_players").insert(items).execute()

    return trade_id


def counter_trade(
    old_trade_id: str,
    actor_team: str,
    proposer_team: str,
    recipient_team: str,
    give_players: List[Dict[str, str]],
    receive_players: List[Dict[str, str]],
    message: str | None = None,
) -> str:
    set_trade_status(old_trade_id, "COUNTERED", actor_team=actor_team)
    return create_trade(
        proposer_team=proposer_team,
        recipient_team=recipient_team,
        give_players=give_players,
        receive_players=receive_players,
        message=message,
        parent_trade_id=old_trade_id,
    )


# ======================================================
# FINALIZE FLOW (JSON on trades row)
# ======================================================
def start_finalize(trade_id: str, actor_team: str):
    trade = get_trade(trade_id)
    if trade["status"] != "PROPOSED":
        raise ValueError("Trade is not PROPOSED.")
    if actor_team != trade["recipient_team"]:
        raise ValueError("Only the recipient can accept/start finalize.")

    now = utc_iso()
    _safe_update_trade_finalize_fields(
        trade_id,
        {
            "status": "FINALIZE_RECIPIENT",
            "recipient_moves": None,
            "proposer_moves": None,
            "recipient_finalized": False,
            "proposer_finalized": False,
            "last_action_by": actor_team,
            "last_action_at": now,
            "updated_at": now,
        },
    )


def save_finalize_moves(trade_id: str, role: str, drops: List[Dict[str, str]], pickups: List[Dict[str, str]]):
    payload = {"drops": drops or [], "pickups": pickups or []}
    now = utc_iso()

    if role == "recipient":
        _safe_update_trade_finalize_fields(
            trade_id,
            {"recipient_moves": payload, "recipient_finalized": True, "updated_at": now, "last_action_at": now},
        )
    elif role == "proposer":
        _safe_update_trade_finalize_fields(
            trade_id,
            {"proposer_moves": payload, "proposer_finalized": True, "updated_at": now, "last_action_at": now},
        )
    else:
        raise ValueError("role must be 'recipient' or 'proposer'")


def load_moves(trade_row: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    rec = trade_row.get("recipient_moves") or {"drops": [], "pickups": []}
    pro = trade_row.get("proposer_moves") or {"drops": [], "pickups": []}
    return rec, pro


# ======================================================
# ROSTER / LINEUP INTEGRITY
# ======================================================
def pos_group(pos_val: Any) -> str:
    if pos_val is None:
        return "F"
    p = str(pos_val).upper()
    if "G" in p:
        return "G"
    if "D" in p:
        return "D"
    return "F"


def count_roster(team_name: str) -> int:
    data = supabase.table("players").select("Name").eq("held_by", team_name).execute().data or []
    return len(data)


def compute_trade_needs(trade_id: str) -> Dict[str, Dict[str, int]]:
    """
    post_count: after swap, before drops/picks
    required_drops: max(0, post_count - 17)
    open_slots: max(0, 17 - post_count)  -> REQUIRED pickups
    """
    trade = get_trade(trade_id)
    items = load_trade_players(trade_id)

    out: Dict[str, Dict[str, int]] = {}
    for team_name in [trade["proposer_team"], trade["recipient_team"]]:
        current_count = count_roster(team_name)
        incoming = int((items["to_team"] == team_name).sum()) if not items.empty else 0
        outgoing = int((items["from_team"] == team_name).sum()) if not items.empty else 0
        post_count = current_count + incoming - outgoing

        required_drops = max(0, post_count - ROSTER_TOTAL)
        open_slots = max(0, ROSTER_TOTAL - post_count)

        out[team_name] = {"post_count": int(post_count), "required_drops": int(required_drops), "open_slots": int(open_slots)}
    return out


def simulate_post_trade_roster(players_df: pd.DataFrame, team_name: str, items_df: pd.DataFrame) -> pd.DataFrame:
    current = players_df[players_df["held_by_norm"] == team_name].copy()

    outgoing = items_df.loc[items_df["from_team"] == team_name, ["player_name", "player_team"]].copy()
    if not outgoing.empty and not current.empty:
        current["_key"] = list(zip(current["Name"], current["team"]))
        out_keys = set(zip(outgoing["player_name"], outgoing["player_team"]))
        current = current[~current["_key"].isin(out_keys)].drop(columns=["_key"])

    incoming = items_df.loc[items_df["to_team"] == team_name, ["player_name", "player_team"]].copy()
    if not incoming.empty:
        tmp = players_df.copy()
        tmp["_key"] = list(zip(tmp["Name"], tmp["team"]))
        inc_keys = set(zip(incoming["player_name"], incoming["player_team"]))
        inc_rows = tmp[tmp["_key"].isin(inc_keys)].drop(columns=["_key"])
        current = pd.concat([current, inc_rows], ignore_index=True)

    current = current.drop_duplicates(subset=["Name", "team"], keep="first")
    return current.reset_index(drop=True)


def rebuild_lineup_state_fixed(team_name: str):
    """
    Rebuild lineup_state to fixed starters 6F/4D/2G.
    Prefers keeping existing starters when possible.
    Also writes Pos. + team from players table.
    """
    current_ls = supabase.table("lineup_state").select("*").eq("team_name", team_name).execute().data or []
    was_starter = {r.get("player_name"): (r.get("player_pos") == "starter") for r in current_ls}

    roster = supabase.table("players").select("*").eq("held_by", team_name).execute().data or []
    if not roster:
        supabase.table("lineup_state").delete().eq("team_name", team_name).execute()
        return

    pools: Dict[str, List[Dict[str, Any]]] = {"F": [], "D": [], "G": []}
    for p in roster:
        pools.setdefault(pos_group(p.get("Pos.")), []).append(p)

    for g in pools:
        pools[g].sort(key=lambda x: (not was_starter.get(x.get("Name"), False), str(x.get("Name"))))

    starter_keys: set[tuple[str, str]] = set()
    for g, need in STARTERS_BY_GROUP.items():
        for p in pools.get(g, [])[: int(need)]:
            starter_keys.add((p.get("Name"), p.get("team")))

    new_rows = []
    for p in roster:
        nm, tm = p.get("Name"), p.get("team")
        new_rows.append(
            {
                "team_name": team_name,
                "player_name": nm,
                "player_pos": "starter" if (nm, tm) in starter_keys else "bench",
                "Pos.": p.get("Pos."),
                "team": tm,
            }
        )

    supabase.table("lineup_state").delete().eq("team_name", team_name).execute()
    supabase.table("lineup_state").insert(new_rows).execute()


def verify_trade_ownership(items_df: pd.DataFrame):
    problems: List[str] = []
    for _, r in items_df.iterrows():
        rec = (
            supabase.table("players")
            .select("Name, team, held_by")
            .eq("Name", r["player_name"])
            .eq("team", r["player_team"])
            .execute()
            .data
        )
        if not rec:
            problems.append(f'{r["player_name"]} ({r["player_team"]}) not found.')
            continue
        if rec[0].get("held_by") != r["from_team"]:
            problems.append(
                f'{r["player_name"]} expected held_by={r["from_team"]}, but is held_by={rec[0].get("held_by")}'
            )
    if problems:
        raise ValueError("Cannot execute trade:\n- " + "\n- ".join(problems))


def execute_trade_balanced(trade_id: str, drops_by_team: Dict[str, List[Dict[str, str]]], pickups_by_team: Dict[str, List[Dict[str, str]]]):
    trade = get_trade(trade_id)
    proposer = trade["proposer_team"]
    recipient = trade["recipient_team"]

    items = load_trade_players(trade_id)
    if items.empty:
        raise ValueError("Trade has no players.")
    verify_trade_ownership(items)

    needs = compute_trade_needs(trade_id)

    # validate: drops exact, pickups exact (open_slots)
    for team_name in [proposer, recipient]:
        req_drops = needs[team_name]["required_drops"]
        req_picks = needs[team_name]["open_slots"]
        drops = drops_by_team.get(team_name, [])
        picks = pickups_by_team.get(team_name, [])
        if len(drops) != req_drops:
            raise ValueError(f"{team_name} must drop exactly {req_drops} player(s).")
        if len(picks) != req_picks:
            raise ValueError(f"{team_name} must pick up exactly {req_picks} free agent(s).")

    # 1) swap ownership
    for _, r in items.iterrows():
        supabase.table("players").update({"held_by": r["to_team"]}).eq("Name", r["player_name"]).eq("team", r["player_team"]).execute()

    # 2) apply drops
    for team_name, drops in drops_by_team.items():
        for p in drops:
            supabase.table("players").update({"held_by": None}).eq("Name", p["Name"]).eq("team", p["team"]).execute()
            supabase.table("lineup_state").delete().eq("team_name", team_name).eq("player_name", p["Name"]).execute()

    # 3) apply pickups (must be free agents)
    for team_name, picks in pickups_by_team.items():
        for p in picks:
            held = supabase.table("players").select("held_by").eq("Name", p["Name"]).eq("team", p["team"]).execute().data
            if not held:
                raise ValueError(f'Pickup player not found: {p["Name"]} ({p["team"]})')
            if held[0].get("held_by") is not None:
                raise ValueError(f'Pickup not available (already owned): {p["Name"]} ({p["team"]})')

            supabase.table("players").update({"held_by": team_name}).eq("Name", p["Name"]).eq("team", p["team"]).execute()

            # upsert as bench (rebuild fixes starters/bench)
            prec = supabase.table("players").select("*").eq("Name", p["Name"]).eq("team", p["team"]).execute().data
            pos_val = prec[0].get("Pos.") if prec else None
            supabase.table("lineup_state").upsert(
                {
                    "team_name": team_name,
                    "player_name": p["Name"],
                    "player_pos": "bench",
                    "Pos.": pos_val,
                    "team": p["team"],
                }
            ).execute()

    # 4) rebuild lineup_state for integrity
    rebuild_lineup_state_fixed(proposer)
    rebuild_lineup_state_fixed(recipient)


def submit_finalize_step(trade_id: str, actor_team: str, drops: List[Dict[str, str]], pickups: List[Dict[str, str]]) -> str:
    trade = get_trade(trade_id)
    proposer = trade["proposer_team"]
    recipient = trade["recipient_team"]

    needs = compute_trade_needs(trade_id)

    if actor_team == recipient:
        if trade["status"] != "FINALIZE_RECIPIENT":
            raise ValueError("Trade is not waiting on recipient finalize.")
        role = "recipient"
    elif actor_team == proposer:
        if trade["status"] != "FINALIZE_PROPOSER":
            raise ValueError("Trade is not waiting on proposer finalize.")
        role = "proposer"
    else:
        raise ValueError("You are not part of this trade.")

    req_drops = needs[actor_team]["required_drops"]
    req_picks = needs[actor_team]["open_slots"]

    if len(drops) != req_drops:
        raise ValueError(f"{actor_team} must drop exactly {req_drops} player(s).")
    if len(pickups) != req_picks:
        raise ValueError(f"{actor_team} must pick up exactly {req_picks} free agent(s).")

    save_finalize_moves(trade_id, role, drops, pickups)

    now = utc_iso()
    if trade["status"] == "FINALIZE_RECIPIENT":
        _safe_update_trade_finalize_fields(
            trade_id,
            {"status": "FINALIZE_PROPOSER", "last_action_by": actor_team, "last_action_at": now, "updated_at": now},
        )
        return "WAITING_ON_PROPOSER"

    # proposer step -> execute
    trade2 = get_trade(trade_id)
    rec_moves, pro_moves = load_moves(trade2)

    execute_trade_balanced(
        trade_id,
        drops_by_team={recipient: rec_moves.get("drops", []), proposer: pro_moves.get("drops", [])},
        pickups_by_team={recipient: rec_moves.get("pickups", []), proposer: pro_moves.get("pickups", [])},
    )
    set_trade_status(trade_id, "ACCEPTED", actor_team=actor_team)
    return "EXECUTED"


# ======================================================
# UI HELPERS
# ======================================================
def strip_internal_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # keep held_by_norm; drop held_by from display if you want
    if "held_by" in out.columns:
        out = out.drop(columns=["held_by"])
    return out


def selectable_editor(df: pd.DataFrame, key: str, checkbox_label: str, title: str) -> List[Dict[str, str]]:
    st.markdown(f"### {title}")
    if df is None or df.empty:
        st.info("No players.")
        return []

    preferred = [c for c in ["Name", "Pos.", "team", "WeeklyPts", "CumulativePts"] if c in df.columns]
    compact = df[preferred].copy() if preferred else df[["Name", "team"]].copy()

    ed = compact.copy()
    ed.insert(0, checkbox_label, False)

    edited = st.data_editor(
        ed,
        key=key,
        hide_index=True,
        disabled=[c for c in ed.columns if c != checkbox_label],
        use_container_width=True,
        height=360,
    )

    with st.expander("Show full columns"):
        st.dataframe(strip_internal_cols(df), hide_index=True, use_container_width=True)

    chosen = edited[edited[checkbox_label] == True]
    if chosen.empty:
        return []
    return chosen[["Name", "team"]].to_dict(orient="records")


def trade_items_with_player_columns(players_df: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    if items.empty:
        return items

    meta = strip_internal_cols(players_df).copy()
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


def clear_ui_caches():
    # clear common keys used by other pages + refresh cached pulls
    for k in ["players", "lineup_state", "roster", "starters", "bench"]:
        st.session_state.pop(k, None)
    st.cache_data.clear()


# ======================================================
# MAIN DATA
# ======================================================
teams_df = load_teams_df()
players_display = build_players_display_df()

if teams_df.empty:
    st.warning("No teams found (teams table is empty).")
    st.stop()

team_names = teams_df["team_name"].tolist()
default_my_team = st.session_state.get("team_name", team_names[0])

# ======================================================
# PROPOSE TRADE
# ======================================================
st.subheader("📨 Propose a Trade")

c1, c2 = st.columns(2)
with c1:
    my_team = st.selectbox("Your team", team_names, index=team_names.index(default_my_team))
with c2:
    partner_choices = [t for t in team_names if t != my_team]
    partner_team = st.selectbox("Trade partner", partner_choices)

my_roster = players_display[players_display["held_by_norm"] == my_team].copy()
partner_roster = players_display[players_display["held_by_norm"] == partner_team].copy()

give_players = selectable_editor(my_roster, key="give_editor", checkbox_label="Send", title=f"{my_team} roster (SEND)")
st.divider()
receive_players = selectable_editor(partner_roster, key="recv_editor", checkbox_label="Receive", title=f"{partner_team} roster (RECEIVE)")

message = st.text_input("Message (optional)", placeholder="e.g., Need a goalie — willing to move a top forward")

p1, p2 = st.columns([1, 1])
with p1:
    if st.button("📨 Propose Trade", disabled=(len(give_players) + len(receive_players) == 0)):
        try:
            tid = create_trade(
                proposer_team=my_team,
                recipient_team=partner_team,
                give_players=give_players,
                receive_players=receive_players,
                message=message or None,
            )
            st.success(f"Trade proposed (id={tid})")
            clear_ui_caches()
            st.rerun()
        except Exception as e:
            st.error(str(e))

with p2:
    if st.button("🧹 Clear selections"):
        for k in ["give_editor", "recv_editor"]:
            st.session_state.pop(k, None)
        st.rerun()

st.divider()

# ======================================================
# TRADE INBOX
# ======================================================
st.subheader("📬 Trades")

viewer_team = st.selectbox("View trades for team", team_names, index=team_names.index(my_team))
trades_df = load_trades_for_team(viewer_team)

if trades_df.empty:
    st.info("No trades yet.")
    st.stop()

trades_df = trades_df.sort_values("created_at", ascending=False)

for _, t in trades_df.iterrows():
    trade_id = t["id"]
    status = t["status"]
    proposer = t["proposer_team"]
    recipient = t["recipient_team"]
    created_at = str(t.get("created_at", ""))[:19].replace("T", " ")
    msg = t.get("message") or ""

    is_recipient_viewing = (viewer_team == recipient)
    is_proposer_viewing = (viewer_team == proposer)

    with st.expander(f"{created_at} — {proposer} ➜ {recipient} | {status}"):
        if msg:
            st.caption(msg)

        items = load_trade_players(trade_id)
        if items.empty:
            st.warning("No players on this trade.")
            continue

        proposer_sends = items[items["from_team"] == proposer].copy()
        recipient_sends = items[items["from_team"] == recipient].copy()

        st.markdown(f"### {proposer} sends")
        st.dataframe(trade_items_with_player_columns(players_display, proposer_sends), hide_index=True, use_container_width=True)
        st.markdown(f"### {recipient} sends")
        st.dataframe(trade_items_with_player_columns(players_display, recipient_sends), hide_index=True, use_container_width=True)

        a1, a2, a3 = st.columns(3)

        # -----------------------
        # PROPOSED actions
        # -----------------------
        if status == "PROPOSED":
            if is_recipient_viewing:
                if a1.button("✅ Accept", key=f"accept_{trade_id}"):
                    try:
                        needs = compute_trade_needs(trade_id)
                        no_balancing_needed = (
                            needs[proposer]["required_drops"] == 0
                            and needs[recipient]["required_drops"] == 0
                            and needs[proposer]["open_slots"] == 0
                            and needs[recipient]["open_slots"] == 0
                        )

                        if no_balancing_needed:
                            execute_trade_balanced(
                                trade_id,
                                drops_by_team={proposer: [], recipient: []},
                                pickups_by_team={proposer: [], recipient: []},
                            )
                            set_trade_status(trade_id, "ACCEPTED", actor_team=viewer_team)
                            clear_ui_caches()
                            st.success("Trade accepted and executed (no balancing needed).")
                            st.rerun()
                        else:
                            start_finalize(trade_id, viewer_team)
                            clear_ui_caches()
                            st.rerun()
                    except Exception as e:
                        st.error(str(e))

                if a2.button("❌ Decline", key=f"decline_{trade_id}"):
                    try:
                        set_trade_status(trade_id, "DECLINED", actor_team=viewer_team)
                        clear_ui_caches()
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

                if a3.button("🔁 Counter", key=f"counter_{trade_id}"):
                    st.session_state["counter_trade_id"] = trade_id
                    st.rerun()

            if is_proposer_viewing:
                if a3.button("🛑 Cancel", key=f"cancel_{trade_id}"):
                    try:
                        set_trade_status(trade_id, "CANCELLED", actor_team=viewer_team)
                        clear_ui_caches()
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        # -----------------------
        # FINALIZE steps
        # -----------------------
        if status in ["FINALIZE_RECIPIENT", "FINALIZE_PROPOSER"]:
            needs = compute_trade_needs(trade_id)
            st.write(
                f"Roster rules: **{ROSTER_TOTAL} total** "
                f"(starters {STARTERS_BY_GROUP['F']}F / {STARTERS_BY_GROUP['D']}D / {STARTERS_BY_GROUP['G']}G, bench {BENCH_TOTAL})."
            )

            post_roster_proposer = simulate_post_trade_roster(players_display, proposer, items)
            post_roster_recipient = simulate_post_trade_roster(players_display, recipient, items)

            # FULL list of free agents
            free_agents_all = players_display[players_display["held_by_norm"] == ""].copy()
            free_agents_all = free_agents_all.drop_duplicates(subset=["Name", "team"], keep="first").reset_index(drop=True)

            fa_query = st.text_input(
                "Search free agents (optional)",
                key=f"fa_q_{trade_id}_{viewer_team}",
                placeholder="Type a name or NHL team abbreviation…",
            )
            free_agents = free_agents_all
            if fa_query:
                q = fa_query.lower()
                free_agents = free_agents_all[
                    free_agents_all["Name"].astype(str).str.lower().str.contains(q)
                    | free_agents_all["team"].astype(str).str.lower().str.contains(q)
                ].copy()

            tr_full = get_trade(trade_id)
            rec_moves, pro_moves = load_moves(tr_full)

            if status == "FINALIZE_RECIPIENT":
                if is_recipient_viewing:
                    st.warning("Step 1 of 2: **Recipient** finalizes first, then it kicks back to proposer.")

                    req_drops = needs[recipient]["required_drops"]
                    req_picks = needs[recipient]["open_slots"]  # REQUIRED

                    st.write(f"Recipient post-trade roster count: **{needs[recipient]['post_count']}**")
                    st.write(f"Required drops: **{req_drops}** | Required pickups: **{req_picks}**")

                    drops = []
                    picks = []

                    if req_drops > 0:
                        drops = selectable_editor(
                            post_roster_recipient,
                            key=f"rec_drops_{trade_id}",
                            checkbox_label="Drop",
                            title=f"{recipient} — REQUIRED drops (exactly {req_drops})",
                        )
                    else:
                        st.caption("No drops required.")

                    if req_picks > 0:
                        picks = selectable_editor(
                            free_agents,
                            key=f"rec_picks_{trade_id}",
                            checkbox_label="Pick up",
                            title=f"{recipient} — REQUIRED pickups (exactly {req_picks})",
                        )
                    else:
                        st.caption("No pickups required.")

                    errs = []
                    if len(drops) != req_drops:
                        errs.append(f"Select exactly {req_drops} drop(s).")
                    if len(picks) != req_picks:
                        errs.append(f"Select exactly {req_picks} pickup(s).")

                    if errs:
                        st.warning("Cannot submit:\n- " + "\n- ".join(errs))

                    if st.button("📨 Submit Recipient Finalize", key=f"submit_rec_{trade_id}", disabled=bool(errs)):
                        try:
                            submit_finalize_step(trade_id, viewer_team, drops=drops, pickups=picks)
                            clear_ui_caches()
                            st.success("Submitted. Now waiting on proposer.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                else:
                    st.info("Waiting on recipient to finalize moves.")
                    st.json(rec_moves)

            if status == "FINALIZE_PROPOSER":
                if is_proposer_viewing:
                    st.warning("Step 2 of 2: **Proposer** finalizes. Submitting executes the trade.")
                    st.caption("Recipient submitted moves (read-only):")
                    st.json(rec_moves)

                    req_drops = needs[proposer]["required_drops"]
                    req_picks = needs[proposer]["open_slots"]  # REQUIRED

                    st.write(f"Proposer post-trade roster count: **{needs[proposer]['post_count']}**")
                    st.write(f"Required drops: **{req_drops}** | Required pickups: **{req_picks}**")

                    drops = []
                    picks = []

                    if req_drops > 0:
                        drops = selectable_editor(
                            post_roster_proposer,
                            key=f"pro_drops_{trade_id}",
                            checkbox_label="Drop",
                            title=f"{proposer} — REQUIRED drops (exactly {req_drops})",
                        )
                    else:
                        st.caption("No drops required.")

                    if req_picks > 0:
                        picks = selectable_editor(
                            free_agents,
                            key=f"pro_picks_{trade_id}",
                            checkbox_label="Pick up",
                            title=f"{proposer} — REQUIRED pickups (exactly {req_picks})",
                        )
                    else:
                        st.caption("No pickups required.")

                    errs = []
                    if len(drops) != req_drops:
                        errs.append(f"Select exactly {req_drops} drop(s).")
                    if len(picks) != req_picks:
                        errs.append(f"Select exactly {req_picks} pickup(s).")

                    if errs:
                        st.warning("Cannot submit:\n- " + "\n- ".join(errs))

                    if st.button("✅ Finalize & Execute Trade", key=f"submit_pro_{trade_id}", disabled=bool(errs)):
                        try:
                            submit_finalize_step(trade_id, viewer_team, drops=drops, pickups=picks)
                            clear_ui_caches()
                            st.success("Trade executed.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                else:
                    st.info("Waiting on proposer to finalize moves.")
                    st.json(pro_moves)

        # -----------------------
        # COUNTER UI
        # -----------------------
        if st.session_state.get("counter_trade_id") == trade_id:
            st.markdown("---")
            st.subheader("Build Counter Offer")

            new_proposer = viewer_team
            new_recipient = proposer  # counter back to original proposer

            my_roster2 = players_display[players_display["held_by_norm"] == new_proposer].copy()
            their_roster2 = players_display[players_display["held_by_norm"] == new_recipient].copy()

            ctr_give = selectable_editor(my_roster2, key=f"ctr_give_{trade_id}", checkbox_label="Send", title=f"{new_proposer} roster (SEND)")
            st.divider()
            ctr_recv = selectable_editor(their_roster2, key=f"ctr_recv_{trade_id}", checkbox_label="Receive", title=f"{new_recipient} roster (RECEIVE)")



            cbtn1, cbtn2 = st.columns(2)
            if cbtn1.button("📨 Submit Counter", key=f"ctr_submit_{trade_id}", disabled=(len(ctr_give) + len(ctr_recv) == 0)):
                try:
                    new_id = counter_trade(
                        old_trade_id=trade_id,
                        actor_team=viewer_team,
                        proposer_team=new_proposer,
                        recipient_team=new_recipient,
                        give_players=ctr_give,
                        receive_players=ctr_recv,
                        message=ctr_msg or None,
                    )
                    st.success(f"Counter sent (id={new_id})")
                    st.session_state.pop("counter_trade_id", None)
                    clear_ui_caches()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if cbtn2.button("Nevermind", key=f"ctr_cancel_{trade_id}"):
                st.session_state.pop("counter_trade_id", None)
                st.rerun()
