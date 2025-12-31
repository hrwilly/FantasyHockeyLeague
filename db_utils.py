# db_utils.py
from supabase import create_client
import streamlit as st
import pandas as pd
import time
from datetime import date
from httpx import ReadError

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

def get_team_by_name(team_name: str):
    """Return team row if it exists, otherwise None."""
    response = supabase.table("teams").select("*").eq("team_name", team_name).execute()
    if response.data:
        return response.data[0]
    return None

def add_team(team_name: str, manager: str):
    """Insert a new team into the database."""
    supabase.table("teams").insert({
        "team_name": team_name,
        "manager": manager
    }).execute()

def load_teams():
    res = supabase.table("teams").select("*").execute()
    return pd.DataFrame(res.data)

def load_players(batch_size=100, max_retries=3, delay=2):
    start = 0
    end = batch_size - 1
    all_rows = []

    while True:
        try:
            for attempt in range(max_retries):
                try:
                    response = supabase.table("players").select("*").range(start, end).execute()
                    rows = response.data
                    break  # Success: exit retry loop
                except ReadError as e:
                    time.sleep(delay)
            else:
                break  # Break outer loop if all retries failed

            if not rows:
                break  # No more data

            all_rows.extend(rows)
            start += batch_size
            end += batch_size

        except Exception as e:
            break

    return pd.DataFrame(all_rows)

# --- Load the full draft board ---
def load_draft_board() -> pd.DataFrame:
    """
    Pulls the DraftBoard table from Supabase and returns a DataFrame.
    Columns: Round, Pick, Name, team, Pos., FantasyTeam
    """
    response = supabase.table("DraftBoard").select("*").execute()
    df = pd.DataFrame(response.data)
    return df

def update_draft_pick_full(round_number, pick_number, name, pos, team, fantasy_team):
    supabase.table("DraftBoard").update({
        "Name": name,
        "Pos.": pos,
        "team": team,
        "FantasyTeam": fantasy_team
    }).eq("Round", round_number).eq("Pick", pick_number).eq("FantasyTeam", fantasy_team).execute()

def save_player(row):
    row_clean = row.where(pd.notna(row), None)
    supabase.table("players").upsert(row_clean.to_dict()).execute()

def load_last_week_stats(batch_size=100, max_retries=3, delay=2):
    start = 0
    end = batch_size - 1
    all_rows = []

    while True:
        try:
            for attempt in range(max_retries):
                try:
                    response = supabase.table("last_week_stats").select("*").range(start, end).execute()
                    rows = response.data
                    break  # Success: exit retry loop
                except ReadError as e:
                    time.sleep(delay)
            else:
                break  # Break outer loop if all retries failed

            if not rows:
                break  # No more data

            all_rows.extend(rows)
            start += batch_size
            end += batch_size

        except Exception as e:
            break

    return pd.DataFrame(all_rows)


def save_last_week_stats(df: pd.DataFrame):
    if df.empty:
        return

    df = df.reset_index()
    supabase.table("last_week_stats").delete().neq("Name", "").execute()
    data = df.to_dict(orient="records")
    supabase.table("last_week_stats").insert(data).execute()


def save_weekly_points(df, week, day):
    """
    Saves (upserts) weekly fantasy points to the 'points' table in Supabase.
    Expects DataFrame columns: Name, team, FantasyPoints.
    """
    if df.empty:
        print("[save_weekly_points] No data to save.")
        return None

    # Copy to avoid modifying original
    df = df.copy()
    df['Week'] = week
    df['Day'] = day
    
    # Convert to list of dicts for Supabase
    records = df.to_dict(orient="records")
    supabase.table("points").upsert(records).execute()

def load_points(batch_size=100, max_retries=3, delay=2):
    start = 0
    end = batch_size - 1
    all_rows = []

    while True:
        try:
            for attempt in range(max_retries):
                try:
                    response = supabase.table("points").select("*").range(start, end).execute()
                    rows = response.data
                    break  # Success: exit retry loop
                except ReadError as e:
                    time.sleep(delay)
            else:
                break  # Break outer loop if all retries failed

            if not rows:
                break  # No more data

            all_rows.extend(rows)
            start += batch_size
            end += batch_size

        except Exception as e:
            break

    return pd.DataFrame(all_rows)

def load_matchups():

    data = supabase.table("matchups").select("*").execute().data
    return pd.DataFrame(data)

def delete_prev_roster(team_name, selected_week):
    supabase.table("active_roster").delete().eq("team_name", team_name).eq("week", selected_week).execute()


def submit_roster(all_rows):
    supabase.table("active_roster").insert(all_rows).execute()

def load_roster():
    table = supabase.table("active_roster")
    page_size = 1000
    start = 0
    all_rows = []

    while True:
        resp = table.select("*").range(start, start + page_size - 1).execute()
        batch = resp.data

        if not batch:
            break

        all_rows.extend(batch)
        start += page_size

        # Stop when fewer than page_size rows are returned
        if len(batch) < page_size:
            break

    return pd.DataFrame(all_rows)

def save_weekly_matchups(week_matchups: pd.DataFrame, week_num):
    """
    Saves weekly matchup results (Week, home_team, away_team, home_team_points, away_team_points)
    into the Supabase 'Matchups' table.
    """

    # --- Select only the needed columns ---
    upload_cols = ["week", "home_team", "away_team", "home_team_points", "away_team_points"]
    upload_df = week_matchups[upload_cols].copy()

    # --- Convert to list of dicts ---
    records = upload_df.to_dict(orient="records")

    # --- Delete any existing records for that week (to prevent duplicates) ---
    supabase.table("matchups").delete().eq("week", week_num).execute()

    # --- Insert new records ---
    supabase.table("matchups").insert(records).execute()

def update_team_record(team_name, W=None, L=None, PF=None, PA=None, Place=None):
    """Update individual team record values in Supabase."""
    updates = {}
    if W is not None:
        updates["W"] = int(W)
    if L is not None:
        updates["L"] = int(L)
    if PF is not None:
        updates["PF"] = float(PF)
    if PA is not None:
        updates["PA"] = float(PA)
    if Place is not None:
        updates["Place"] = int(Place)

    if updates:
        supabase.table("teams").update(updates).eq("team_name", team_name).execute()

    
def load_lineup_state(team_name):
    resp = (
        supabase
        .table("lineup_state")
        .select("*")
        .eq("team_name", team_name)
        .execute()
    )
    return pd.DataFrame(resp.data)

def save_lineup_state(rows):
    """
    rows: list of dicts
    """
    supabase.table("lineup_state").upsert(rows).execute()

def swap_lineup_state(team_name, player_out, player_in):

    supabase.table("lineup_state").update(
        {"player_pos": "bench"}
    ).eq("team_name", team_name) \
     .eq("player_name", player_out) \
     .execute()

    supabase.table("lineup_state").update(
        {"player_pos": "starter"}
    ).eq("team_name", team_name) \
     .eq("player_name", player_in) \
     .execute()

def lock_weekly_rosters(week):
    resp = supabase.table("lineup_state").select("*").execute()
    lineup = resp.data

    if not lineup:
        return

    supabase.table("active_roster").delete().eq("week", week).execute()

    locked = [
        {**row, "week": week}
        for row in lineup
    ]

    supabase.table("active_roster").insert(locked).execute()

def add_drop_player(
    team_name,
    add_player,
    drop_player,
    add_player_pos,
    add_player_team,
    starter=False
):
    """
    Handles add/drop consistently across players + lineup_state
    """

    # --- Update ownership ---
    supabase.table("players").update(
        {"held_by": team_name}
    ).eq("Name", add_player).execute()

    supabase.table("players").update(
        {"held_by": None}
    ).eq("Name", drop_player).execute()

    # --- Remove dropped player from lineup ---
    supabase.table("lineup_state").delete() \
        .eq("team_name", team_name) \
        .eq("player_name", drop_player) \
        .execute()

    # --- Insert added player into lineup ---
    supabase.table("lineup_state").upsert({
        "team_name": team_name,
        "player_name": add_player,
        "player_pos": "starter" if starter else "bench",
        "Pos.": add_player_pos,
        "team": add_player_team
    }).execute()

def load_players_for_team(team_name: str, batch_size=500, max_retries=3, delay=1):
    """
    Loads only players owned by a single fantasy team (players.held_by == team_name).
    Uses pagination for safety but the result set should be small.
    """
    start = 0
    end = batch_size - 1
    all_rows = []

    while True:
        rows = None

        for attempt in range(max_retries):
            try:
                resp = (
                    supabase
                    .table("players")
                    .select("*")
                    .eq("held_by", team_name)
                    .range(start, end)
                    .execute()
                )
                rows = resp.data
                break
            except ReadError:
                time.sleep(delay)

        # If request never succeeded, stop
        if rows is None:
            break

        if not rows:
            break

        all_rows.extend(rows)

        # advance pagination
        start += batch_size
        end += batch_size

        # stop if last page
        if len(rows) < batch_size:
            break

    return pd.DataFrame(all_rows)

# db_utils.py
# Minimal, trade-focused db_utils that supports:
# - loading teams/players/points/last_week_stats (used by Trades page)
# - proposing/countering trades
# - multi-step finalize WITHOUT a new table (stores moves on trades row as JSON)
# - executing uneven trades with mandatory drops + optional pickups
# - rebuilding lineup_state to fixed roster rules (6F/4D/2G starters, 5 bench = 17)
#
# REQUIREMENTS IN SUPABASE:
# 1) trades.status must allow:
#    PROPOSED, FINALIZE_RECIPIENT, FINALIZE_PROPOSER, ACCEPTED, DECLINED, CANCELLED, COUNTERED
# 2) trades table has columns (JSONB):
#    recipient_moves jsonb, proposer_moves jsonb
#    (optional but supported) recipient_finalized boolean, proposer_finalized boolean
# 3) lineup_state columns at least:
#    team_name (text), player_name (text), player_pos (text: 'starter'/'bench'), "Pos." (text), team (text)
# 4) players columns at least:
#    Name (text), team (text), held_by (text nullable), "Pos." (text)
#
# NOTE ABOUT "Pos.": PostgREST chokes on select("Pos.") so we always select("*") when we need it.


# ===========================
# CONFIG: ROSTER RULES
# ===========================
STARTERS_BY_GROUP = {"F": 6, "D": 4, "G": 2}  # fixed starters
ROSTER_TOTAL = 17
STARTER_TOTAL = sum(STARTERS_BY_GROUP.values())
BENCH_TOTAL = ROSTER_TOTAL - STARTER_TOTAL

TRADE_STATUSES = [
    "PROPOSED",
    "FINALIZE_RECIPIENT",
    "FINALIZE_PROPOSER",
    "ACCEPTED",
    "DECLINED",
    "CANCELLED",
    "COUNTERED",
]


# ===========================
# TRADE CRUD
# ===========================
def create_trade(
    proposer_team: str,
    recipient_team: str,
    give_players: list[dict],
    receive_players: list[dict],
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
        "last_action_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        # Multi-step finalize fields (safe to include even if columns don’t exist yet)
        "recipient_moves": None,
        "proposer_moves": None,
        "recipient_finalized": False,
        "proposer_finalized": False,
    }

    trade_resp = _sb().table("trades").insert(trade_row).execute()
    trade_id = trade_resp.data[0]["id"]

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
        _sb().table("trade_players").insert(items).execute()

    return trade_id


def counter_trade(
    old_trade_id: str,
    actor_team: str,
    proposer_team: str,
    recipient_team: str,
    give_players: list[dict],
    receive_players: list[dict],
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


def load_trades_for_team(team_name: str) -> pd.DataFrame:
    resp = (
        _sb()
        .table("trades")
        .select("*")
        .or_(f"proposer_team.eq.{team_name},recipient_team.eq.{team_name}")
        .order("created_at", desc=True)
        .execute()
    )
    return pd.DataFrame(resp.data or [])


def load_trade_players(trade_id: str) -> pd.DataFrame:
    resp = _sb().table("trade_players").select("*").eq("trade_id", trade_id).execute()
    return pd.DataFrame(resp.data or [])


def get_trade(trade_id: str) -> dict[str, Any]:
    return _sb().table("trades").select("*").eq("id", trade_id).execute().data[0]


def set_trade_status(trade_id: str, status: str, actor_team: str):
    if status not in TRADE_STATUSES:
        raise ValueError(f"Invalid trade status: {status}")

    updates = {
        "status": status,
        "last_action_by": actor_team,
        "last_action_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }
    _sb().table("trades").update(updates).eq("id", trade_id).execute()


# ===========================
# MULTI-STEP FINALIZE (no new table)
# ===========================
def _save_finalize_moves(trade_id: str, role: str, drops: list[dict], pickups: list[dict]):
    payload = {"drops": drops or [], "pickups": pickups or []}
    now = _utc_now_iso()

    if role == "recipient":
        _sb().table("trades").update(
            {
                "recipient_moves": payload,
                "recipient_finalized": True,
                "updated_at": now,
                "last_action_at": now,
            }
        ).eq("id", trade_id).execute()
    elif role == "proposer":
        _sb().table("trades").update(
            {
                "proposer_moves": payload,
                "proposer_finalized": True,
                "updated_at": now,
                "last_action_at": now,
            }
        ).eq("id", trade_id).execute()
    else:
        raise ValueError("role must be 'recipient' or 'proposer'")


def _load_moves(trade_row: dict) -> tuple[dict, dict]:
    rec = trade_row.get("recipient_moves") or {"drops": [], "pickups": []}
    pro = trade_row.get("proposer_moves") or {"drops": [], "pickups": []}
    return rec, pro


def compute_trade_needs(trade_id: str) -> dict[str, dict[str, int]]:
    """
    For each team: post_count after trade (before balancing), required_drops, open_slots
    """
    trade = get_trade(trade_id)
    items = load_trade_players(trade_id)

    out: dict[str, dict[str, int]] = {}
    for team_name in [trade["proposer_team"], trade["recipient_team"]]:
        # count current roster size (len fallback is safer than relying on .count across client versions)
        cur = _sb().table("players").select("Name").eq("held_by", team_name).execute().data or []
        current_count = len(cur)

        incoming = int((items["to_team"] == team_name).sum()) if not items.empty else 0
        outgoing = int((items["from_team"] == team_name).sum()) if not items.empty else 0
        post_count = current_count + incoming - outgoing

        required_drops = max(0, post_count - ROSTER_TOTAL)
        open_slots = max(0, ROSTER_TOTAL - post_count)
        out[team_name] = {
            "post_count": int(post_count),
            "required_drops": int(required_drops),
            "open_slots": int(open_slots),
        }

    return out


def start_finalize(trade_id: str, actor_team: str):
    """
    Recipient clicks accept -> trade moves to FINALIZE_RECIPIENT and clears prior finalize data.
    """
    trade = get_trade(trade_id)
    if trade["status"] != "PROPOSED":
        raise ValueError("Trade is not PROPOSED.")
    if actor_team != trade["recipient_team"]:
        raise ValueError("Only the recipient can start finalize.")

    now = _utc_now_iso()
    _sb().table("trades").update(
        {
            "status": "FINALIZE_RECIPIENT",
            "recipient_finalized": False,
            "proposer_finalized": False,
            "recipient_moves": None,
            "proposer_moves": None,
            "updated_at": now,
            "last_action_by": actor_team,
            "last_action_at": now,
        }
    ).eq("id", trade_id).execute()


def submit_finalize_step(trade_id: str, actor_team: str, drops: list[dict], pickups: list[dict]) -> str:
    """
    Step 1: recipient submits -> status FINALIZE_PROPOSER
    Step 2: proposer submits -> execute_trade_balanced + status ACCEPTED
    """
    trade = get_trade(trade_id)
    proposer = trade["proposer_team"]
    recipient = trade["recipient_team"]

    needs = compute_trade_needs(trade_id)
    if actor_team == recipient:
        role = "recipient"
        required = needs[recipient]["required_drops"]
        open_slots = needs[recipient]["open_slots"]
        if trade["status"] != "FINALIZE_RECIPIENT":
            raise ValueError("Trade is not waiting on recipient finalize.")
    elif actor_team == proposer:
        role = "proposer"
        required = needs[proposer]["required_drops"]
        open_slots = needs[proposer]["open_slots"]
        if trade["status"] != "FINALIZE_PROPOSER":
            raise ValueError("Trade is not waiting on proposer finalize.")
    else:
        raise ValueError("You are not part of this trade.")

    if len(drops) != required:
        raise ValueError(f"{actor_team} must drop exactly {required} player(s).")
    if len(pickups) > open_slots:
        raise ValueError(f"{actor_team} can pick up at most {open_slots} player(s).")

    _save_finalize_moves(trade_id, role, drops, pickups)

    # advance or execute
    now = _utc_now_iso()
    if trade["status"] == "FINALIZE_RECIPIENT":
        _sb().table("trades").update(
            {
                "status": "FINALIZE_PROPOSER",
                "updated_at": now,
                "last_action_by": actor_team,
                "last_action_at": now,
            }
        ).eq("id", trade_id).execute()
        return "WAITING_ON_PROPOSER"

    # proposer step -> execute once
    trade2 = get_trade(trade_id)
    rec_moves, pro_moves = _load_moves(trade2)

    execute_trade_balanced(
        trade_id,
        drops_by_team={
            recipient: rec_moves.get("drops", []),
            proposer: pro_moves.get("drops", []),
        },
        pickups_by_team={
            recipient: rec_moves.get("pickups", []),
            proposer: pro_moves.get("pickups", []),
        },
    )
    set_trade_status(trade_id, "ACCEPTED", actor_team=actor_team)
    return "EXECUTED"


# ===========================
# EXECUTION: BALANCED TRADE + LINEUP REBUILD
# ===========================
def _pos_group(pos_val: str | None) -> str:
    if not pos_val:
        return "F"
    p = str(pos_val).upper()
    if "G" in p:
        return "G"
    if "D" in p:
        return "D"
    return "F"


def _player_row(name: str, team: str) -> dict[str, Any] | None:
    # select("*") avoids PostgREST parsing issue for "Pos."
    data = _sb().table("players").select("*").eq("Name", name).eq("team", team).execute().data or []
    return data[0] if data else None


def _verify_trade_ownership(items: pd.DataFrame) -> None:
    problems: list[str] = []
    for _, row in items.iterrows():
        rec = (
            _sb()
            .table("players")
            .select("Name, team, held_by")
            .eq("Name", row["player_name"])
            .eq("team", row["player_team"])
            .execute()
            .data
        )
        if not rec:
            problems.append(f'{row["player_name"]} ({row["player_team"]}) not found.')
            continue
        if rec[0].get("held_by") != row["from_team"]:
            problems.append(
                f'{row["player_name"]} expected held_by={row["from_team"]}, but is held_by={rec[0].get("held_by")}'
            )
    if problems:
        raise ValueError("Cannot execute trade:\n- " + "\n- ".join(problems))


def _rebuild_lineup_state_fixed(team_name: str):
    """
    Force lineup_state to match fixed starters (6F/4D/2G) and bench for the rest.
    Prefers keeping existing starters if possible.
    Also ensures Pos. and team columns are correct.
    """
    # current lineup_state: prefer keeping starters
    current_ls = _sb().table("lineup_state").select("*").eq("team_name", team_name).execute().data or []
    was_starter = {r.get("player_name"): (r.get("player_pos") == "starter") for r in current_ls}

    roster = _sb().table("players").select("*").eq("held_by", team_name).execute().data or []
    if not roster:
        _sb().table("lineup_state").delete().eq("team_name", team_name).execute()
        return

    pools: dict[str, list[dict]] = {"F": [], "D": [], "G": []}
    for p in roster:
        pools.setdefault(_pos_group(p.get("Pos.")), []).append(p)

    # starters first, stable by name
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

    # replace rows
    _sb().table("lineup_state").delete().eq("team_name", team_name).execute()
    _sb().table("lineup_state").insert(new_rows).execute()


def execute_trade_balanced(
    trade_id: str,
    drops_by_team: dict[str, list[dict]],
    pickups_by_team: dict[str, list[dict]] | None = None,
):
    """
    Executes a trade AND enforces roster size 17 by requiring drops (and allowing optional pickups).
    - Swaps players.held_by per trade_players
    - Applies drops (held_by -> NULL) and removes from lineup_state
    - Applies pickups (held_by -> team) and inserts into lineup_state as bench initially
    - Rebuilds lineup_state for BOTH teams to fixed starter counts
    """
    pickups_by_team = pickups_by_team or {}

    trade = get_trade(trade_id)
    if trade["status"] not in ["FINALIZE_PROPOSER", "FINALIZE_RECIPIENT", "PROPOSED"]:
        # We allow execution only from finalize states typically, but keep it permissive.
        pass

    items = load_trade_players(trade_id)
    if items.empty:
        raise ValueError("Trade has no players.")
    _verify_trade_ownership(items)

    proposer = trade["proposer_team"]
    recipient = trade["recipient_team"]

    # Validate drop/pick sizes vs computed needs
    needs = compute_trade_needs(trade_id)
    for team_name in [proposer, recipient]:
        req = needs[team_name]["required_drops"]
        open_slots = needs[team_name]["open_slots"]
        drops = drops_by_team.get(team_name, [])
        picks = pickups_by_team.get(team_name, [])
        if len(drops) != req:
            raise ValueError(f"{team_name} must drop exactly {req} player(s).")
        if len(picks) > open_slots:
            raise ValueError(f"{team_name} can pick up at most {open_slots} player(s).")

    # 1) Apply ownership swaps
    for _, row in items.iterrows():
        _sb().table("players").update({"held_by": row["to_team"]}).eq("Name", row["player_name"]).eq(
            "team", row["player_team"]
        ).execute()

    # 2) Drops
    for team_name, drops in (drops_by_team or {}).items():
        for p in drops:
            _sb().table("players").update({"held_by": None}).eq("Name", p["Name"]).eq("team", p["team"]).execute()
            _sb().table("lineup_state").delete().eq("team_name", team_name).eq("player_name", p["Name"]).execute()

    # 3) Pickups
    for team_name, picks in (pickups_by_team or {}).items():
        for p in picks:
            # confirm player is unowned
            held = _sb().table("players").select("held_by").eq("Name", p["Name"]).eq("team", p["team"]).execute().data
            if not held or held[0].get("held_by") is not None:
                raise ValueError(f'Pickup not available: {p["Name"]} ({p["team"]})')

            _sb().table("players").update({"held_by": team_name}).eq("Name", p["Name"]).eq("team", p["team"]).execute()

            prec = _player_row(p["Name"], p["team"])
            _sb().table("lineup_state").upsert(
                {
                    "team_name": team_name,
                    "player_name": p["Name"],
                    "player_pos": "bench",
                    "Pos.": (prec.get("Pos.") if prec else None),
                    "team": p["team"],
                }
            ).execute()

    # 4) Rebuild lineup_state for both teams to fixed counts
    _rebuild_lineup_state_fixed(proposer)
    _rebuild_lineup_state_fixed(recipient)

    # Clear cached loaders so UI refreshes after execution
    st.cache_data.clear()
