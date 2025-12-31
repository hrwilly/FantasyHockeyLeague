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

from typing import List, Dict, Optional
from datetime import datetime

# ======================================================
# TRADES
# ======================================================

TRADE_STATUSES = ["PROPOSED", "ACCEPTED", "DECLINED", "COUNTERED", "CANCELLED"]

def create_trade(
    proposer_team: str,
    recipient_team: str,
    give_players: List[Dict],
    receive_players: List[Dict],
    message: Optional[str] = None,
    parent_trade_id: Optional[str] = None,
):
    """
    give_players/receive_players: list of dicts containing at least:
      {"Name": "...", "team": "..."}  # 'team' here is the real team column in players table
    """
    trade_row = {
        "proposer_team": proposer_team,
        "recipient_team": recipient_team,
        "status": "PROPOSED",
        "message": message,
        "parent_trade_id": parent_trade_id,
        "last_action_by": proposer_team,
        "last_action_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    trade_resp = supabase.table("trades").insert(trade_row).execute()
    trade_id = trade_resp.data[0]["id"]

    items = []
    for p in give_players:
        items.append({
            "trade_id": trade_id,
            "from_team": proposer_team,
            "to_team": recipient_team,
            "player_name": p["Name"],
            "player_team": p["team"],
        })
    for p in receive_players:
        items.append({
            "trade_id": trade_id,
            "from_team": recipient_team,
            "to_team": proposer_team,
            "player_name": p["Name"],
            "player_team": p["team"],
        })

    if items:
        supabase.table("trade_players").insert(items).execute()

    return trade_id


def load_trades_for_team(team_name: str):
    """
    Returns trades where team is proposer or recipient (most recent first).
    """
    resp = (
        supabase.table("trades")
        .select("*")
        .or_(f"proposer_team.eq.{team_name},recipient_team.eq.{team_name}")
        .order("created_at", desc=True)
        .execute()
    )
    return pd.DataFrame(resp.data)


def load_trade_players(trade_id: str):
    resp = (
        supabase.table("trade_players")
        .select("*")
        .eq("trade_id", trade_id)
        .execute()
    )
    return pd.DataFrame(resp.data)


def set_trade_status(trade_id: str, status: str, actor_team: str):
    if status not in TRADE_STATUSES:
        raise ValueError(f"Invalid trade status: {status}")

    updates = {
        "status": status,
        "last_action_by": actor_team,
        "last_action_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    supabase.table("trades").update(updates).eq("id", trade_id).execute()


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


def counter_trade(
    old_trade_id: str,
    actor_team: str,
    proposer_team: str,
    recipient_team: str,
    give_players: List[Dict],
    receive_players: List[Dict],
    message: Optional[str] = None,
):
    """
    Marks old trade COUNTERED and creates a new trade linked via parent_trade_id.
    """
    set_trade_status(old_trade_id, "COUNTERED", actor_team=actor_team)
    return create_trade(
        proposer_team=proposer_team,
        recipient_team=recipient_team,
        give_players=give_players,
        receive_players=receive_players,
        message=message,
        parent_trade_id=old_trade_id,
    )

# ===========================
# ROSTER RULES
# ===========================
STARTERS_BY_GROUP = {"F": 6, "D": 4, "G": 2}  # change if needed
ROSTER_TOTAL = 17
STARTER_TOTAL = sum(STARTERS_BY_GROUP.values())
BENCH_TOTAL = ROSTER_TOTAL - STARTER_TOTAL

def _pos_group(pos_val: str) -> str:
    """Map players['Pos.'] into F/D/G groups."""
    if not pos_val:
        return "F"
    p = str(pos_val).upper()
    # adjust mapping to match your Pos. strings
    if "G" in p:
        return "G"
    if "D" in p:
        return "D"
    return "F"


def _players_select_all_by_held(team_name: str):
    # use select("*") to avoid PostgREST parsing issue with column "Pos."
    return supabase.table("players").select("*").eq("held_by", team_name).execute().data or []


def _free_agents_select_all(limit: int = 200):
    # assumes unowned players have held_by null
    return supabase.table("players").select("*").is_("held_by", "null").limit(limit).execute().data or []


def _trade_items_df(trade_id: str):
    return load_trade_players(trade_id)  # your existing helper returns a DataFrame


def _simulate_post_trade_roster(team_name: str, trade_items_df):
    """
    Returns a list of player dicts (Name, team, Pos.) representing roster
    after applying trade ownership changes (but before drops/pickups).
    """
    current = _players_select_all_by_held(team_name)

    # index current roster by (Name, team)
    roster_map = {(p.get("Name"), p.get("team")): p for p in current}

    # remove outgoing
    outgoing = trade_items_df[trade_items_df["from_team"] == team_name]
    for _, r in outgoing.iterrows():
        roster_map.pop((r["player_name"], r["player_team"]), None)

    # add incoming (pull full player row so Pos. is present)
    incoming = trade_items_df[trade_items_df["to_team"] == team_name]
    for _, r in incoming.iterrows():
        rec = (
            supabase.table("players")
            .select("*")
            .eq("Name", r["player_name"])
            .eq("team", r["player_team"])
            .execute()
            .data
        )
        if rec:
            roster_map[(rec[0].get("Name"), rec[0].get("team"))] = rec[0]

    # normalize output
    out = []
    for p in roster_map.values():
        if p.get("Name") and p.get("team"):
            out.append({"Name": p.get("Name"), "team": p.get("team"), "Pos.": p.get("Pos.")})
    return out


def _rebuild_lineup_state_fixed(team_name: str):
    """
    Force lineup_state to match fixed rules:
      starters: 6F/4D/2G
      bench: everyone else
    Preference: keep existing starters when possible.
    Also writes Pos. + team into lineup_state.
    """
    # current lineup_state to prefer keeping starters
    current_ls = supabase.table("lineup_state").select("*").eq("team_name", team_name).execute().data or []
    was_starter = {r.get("player_name"): (r.get("player_pos") == "starter") for r in current_ls}

    roster = _players_select_all_by_held(team_name)
    if not roster:
        supabase.table("lineup_state").delete().eq("team_name", team_name).execute()
        return

    # build pools by group
    pools = {"F": [], "D": [], "G": []}
    for p in roster:
        pools.setdefault(_pos_group(p.get("Pos.")), []).append(p)

    # sort pools: starters first, then stable by name
    for g in pools:
        pools[g].sort(key=lambda x: (not was_starter.get(x.get("Name"), False), str(x.get("Name"))))

    starters = []
    starter_set = set()

    # pick starters by required group counts
    for g, need in STARTERS_BY_GROUP.items():
        for p in pools.get(g, [])[:int(need)]:
            starters.append(p)
            starter_set.add((p.get("Name"), p.get("team")))

    # (Optional) If roster is missing a group, you could fill with other players,
    # but with your league roster constraints this should rarely happen.

    # rebuild lineup_state rows for ALL rostered players
    new_rows = []
    for p in roster:
        nm, tm = p.get("Name"), p.get("team")
        pos_val = p.get("Pos.")
        new_rows.append({
            "team_name": team_name,
            "player_name": nm,
            "player_pos": "starter" if (nm, tm) in starter_set else "bench",
            "Pos.": pos_val,
            "team": tm,
        })

    supabase.table("lineup_state").delete().eq("team_name", team_name).execute()
    supabase.table("lineup_state").insert(new_rows).execute()


def execute_trade_balanced(trade_id: str, drops_by_team: dict, pickups_by_team: dict | None = None):
    """
    Executes trade AND enforces roster size = 17 via required drops (and optional pickups).
    drops_by_team format: { "Team A": [{"Name":..., "team":...}, ...], "Team B": [...] }
    pickups_by_team format: { "Team A": [{"Name":..., "team":...}], ... }  # optional, can be empty
    """
    pickups_by_team = pickups_by_team or {}

    trade = supabase.table("trades").select("*").eq("id", trade_id).execute().data[0]
    if trade["status"] != "PROPOSED":
        raise ValueError(f"Trade is not PROPOSED (status={trade['status']}).")

    items = _trade_items_df(trade_id)
    if items.empty:
        raise ValueError("Trade has no players.")

    team_a = trade["proposer_team"]
    team_b = trade["recipient_team"]

    # 1) Verify ownership for traded players
    problems = []
    for _, row in items.iterrows():
        current = (
            supabase.table("players")
            .select("Name, team, held_by")
            .eq("Name", row["player_name"])
            .eq("team", row["player_team"])
            .execute()
            .data
        )
        if not current:
            problems.append(f'{row["player_name"]} ({row["player_team"]}) not found.')
            continue
        if current[0].get("held_by") != row["from_team"]:
            problems.append(
                f'{row["player_name"]} expected held_by={row["from_team"]}, '
                f'but is held_by={current[0].get("held_by")}'
            )
    if problems:
        raise ValueError("Cannot execute trade:\n- " + "\n- ".join(problems))

    # 2) Validate roster counts after trade + drops/pickups
    for tname in [team_a, team_b]:
        post = _simulate_post_trade_roster(tname, items)

        incoming = int((items["to_team"] == tname).sum())
        outgoing = int((items["from_team"] == tname).sum())
        current_count = len(_players_select_all_by_held(tname))
        post_count = current_count + incoming - outgoing  # should match len(post)

        req_drops = max(0, post_count - ROSTER_TOTAL)
        open_slots = max(0, ROSTER_TOTAL - post_count)

        chosen_drops = drops_by_team.get(tname, [])
        chosen_picks = pickups_by_team.get(tname, [])

        if len(chosen_drops) != req_drops:
            raise ValueError(f"{tname} must drop exactly {req_drops} player(s) to accept this trade.")

        if len(chosen_picks) > open_slots:
            raise ValueError(f"{tname} can pick up at most {open_slots} player(s).")

        # Ensure drop targets are in the post-trade roster
        post_keys = {(p["Name"], p["team"]) for p in post}
        for p in chosen_drops:
            if (p["Name"], p["team"]) not in post_keys:
                raise ValueError(f'{tname} drop selection includes non-rostered player: {p["Name"]} ({p["team"]})')

        # Ensure pickups are actually free agents
        for p in chosen_picks:
            rec = (
                supabase.table("players")
                .select("held_by")
                .eq("Name", p["Name"])
                .eq("team", p["team"])
                .execute()
                .data
            )
            if not rec or rec[0].get("held_by") is not None:
                raise ValueError(f'Pickup not available: {p["Name"]} ({p["team"]})')

    # 3) Apply trade swaps
    for _, row in items.iterrows():
        supabase.table("players").update(
            {"held_by": row["to_team"]}
        ).eq("Name", row["player_name"]).eq("team", row["player_team"]).execute()

    # 4) Apply drops (set held_by NULL + remove from lineup_state)
    for tname, drops in drops_by_team.items():
        for p in drops:
            supabase.table("players").update({"held_by": None}).eq("Name", p["Name"]).eq("team", p["team"]).execute()
            supabase.table("lineup_state").delete().eq("team_name", tname).eq("player_name", p["Name"]).execute()

    # 5) Apply pickups (held_by team + add to lineup_state as bench for now; rebuild will finalize)
    for tname, picks in pickups_by_team.items():
        for p in picks:
            # attach
            supabase.table("players").update({"held_by": tname}).eq("Name", p["Name"]).eq("team", p["team"]).execute()
            # get Pos. safely
            prec = supabase.table("players").select("*").eq("Name", p["Name"]).eq("team", p["team"]).execute().data
            pos_val = prec[0].get("Pos.") if prec else None
            supabase.table("lineup_state").upsert({
                "team_name": tname,
                "player_name": p["Name"],
                "player_pos": "bench",
                "Pos.": pos_val,
                "team": p["team"],
            }).execute()

    # 6) Rebuild lineup_state for both teams to fixed 6F/4D/2G starters
    _rebuild_lineup_state_fixed(team_a)
    _rebuild_lineup_state_fixed(team_b)

