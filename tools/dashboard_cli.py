#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import curses
import hashlib
import json
import math
import os
import re
import secrets
import sys
import threading
import time
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from src.tui_auth import ensure_tui_auth_session
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

# v2 design-aligned pages
PAGE_ORDER = [
    "overview",
    "mystats",
    "leaderboard",
    "categories",
    "channels",
    "behavior",
    "graph",
    "governance",
    "operations",
]
PAGE_TITLES = {
    "overview": "Overview",
    "mystats": "MyStats",
    "leaderboard": "Leaderboard",
    "categories": "Categories",
    "channels": "Channels",
    "behavior": "Behavior",
    "graph": "Graph",
    "governance": "Governance",
    "operations": "Operations",
}

CATEGORY_ORDER = ["INFO", "INSIGHT", "VIBE", "OPS", "MISC"]
CATEGORY_CP = {"INFO": 5.0, "INSIGHT": 4.0, "VIBE": 3.0, "OPS": 4.0, "MISC": 1.0}

REACTION_GIVE_CP = 1.0
DEFAULT_TS = 100.0
MAX_VP = 6

URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)

OPS_CHANNEL_HINTS = (
    "ops",
    "operation",
    "運営",
    "admin",
    "告知",
    "schedule",
    "task",
    "coord",
)
PROJECT_CHANNEL_HINTS = (
    "開発",
    "dev",
    "project",
    "農業",
    "本のコモンズ",
    "build",
    "tech",
    "engineer",
)
KNOWLEDGE_CHANNEL_HINTS = (
    "学び",
    "learn",
    "study",
    "knowledge",
    "記事",
    "share",
    "news",
    "paper",
)
HOBBY_CHANNEL_HINTS = (
    "ゲーム",
    "game",
    "音楽",
    "music",
    "hobby",
    "movie",
    "anime",
)

DESIGN_TABLES = [
    "members",
    "cp_ledger",
    "ts_events",
    "votes",
    "vote_results",
    "achievements",
    "member_achievements",
    "issues",
    "quests",
]

    new_session = _perform_browser_login(supabase_url, apikey, timeout_sec)
    user = _fetch_auth_user(supabase_url, apikey, new_session["access_token"])
    if user:
        new_session["user"] = user
    _save_session(session_file, new_session)
    return new_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Comm0ns Dashboard CLI (v2 design aligned)"
    )
    parser.add_argument(
        "--section",
        choices=[*PAGE_ORDER, "all"],
        default="overview",
        help="Section for non-TUI mode",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Row limit for ranking-like pages",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Trend days in overview",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=15.0,
        help="Auto refresh interval in seconds for TUI",
    )
    parser.add_argument(
        "--user",
        default="",
        help="Focus user for mystats page (user_id or username)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=90,
        help="How many recent days to scan from DB (default: 90)",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=50000,
        help="Hard cap for scanned messages (default: 50000)",
    )
    parser.add_argument(
        "--max-reactions",
        type=int,
        default=50000,
        help="Hard cap for scanned reactions (default: 50000)",
    )
    parser.add_argument(
        "--max-users",
        type=int,
        default=5000,
        help="Hard cap for tracked users in model (default: 5000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Supabase request timeout seconds (default: 20)",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Run interactive TUI mode",
    )
    parser.add_argument(
        "--skip-auth",
        action="store_true",
        help="Skip Discord OAuth login flow in TUI mode",
    )
    parser.add_argument(
        "--force-login",
        action="store_true",
        help="Ignore saved auth session and force browser login in TUI mode",
    )
    parser.add_argument(
        "--auth-timeout",
        type=int,
        default=_to_int(os.getenv("TUI_AUTH_TIMEOUT"), DEFAULT_AUTH_TIMEOUT),
        help=f"OAuth callback timeout in seconds (default: {DEFAULT_AUTH_TIMEOUT})",
    )
    return parser.parse_args()


def get_client(timeout_sec: float) -> Client:
    load_dotenv()
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_KEY are required in .env", file=sys.stderr)
        sys.exit(1)
    options = SyncClientOptions(postgrest_client_timeout=max(5.0, timeout_sec))
    return create_client(url, key, options=options)


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def render_table_lines(headers: list[str], rows: list[list[Any]], width: int) -> list[str]:
    if not rows:
        return ["(no data)"]

    str_rows = [[str(c) for c in row] for row in rows]
    col_widths = [len(h) for h in headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    lines: list[str] = []
    header_line = " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers)))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    lines.append(clip(header_line, width))
    lines.append(clip(sep_line, width))
    for row in str_rows:
        line = " | ".join(row[i].ljust(col_widths[i]) for i in range(len(headers)))
        lines.append(clip(line, width))
    return lines


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fetch_all_rows(client: Client, table: str, columns: str, chunk_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + chunk_size - 1
        resp = client.table(table).select(columns).range(start, end).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < chunk_size:
            break
        start += chunk_size
    return rows


def try_fetch_all_rows(client: Client, table: str, columns: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return fetch_all_rows(client, table, columns), None
    except Exception as exc:
        return [], str(exc)


def chunked(values: list[int], size: int) -> list[list[int]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def fetch_rows_window(
    client: Client,
    table: str,
    columns: str,
    date_column: str,
    since_dt: datetime,
    max_rows: int,
    chunk_size: int = 1000,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    max_rows = max(1, max_rows)
    while len(rows) < max_rows:
        remaining = max_rows - len(rows)
        take = min(chunk_size, remaining)
        end = start + take - 1
        resp = (
            client.table(table)
            .select(columns)
            .gte(date_column, since_dt.isoformat())
            .order(date_column, desc=True)
            .range(start, end)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < take:
            break
        start += take
    return rows


def fetch_users_by_ids(client: Client, user_ids: list[int]) -> list[dict[str, Any]]:
    if not user_ids:
        return []
    rows: list[dict[str, Any]] = []
    for ids in chunked(user_ids, 400):
        resp = (
            client.table("users")
            .select("user_id,username,current_score,weekly_score")
            .in_("user_id", ids)
            .execute()
        )
        rows.extend(resp.data or [])
    return rows


def fetch_members_ts_by_ids(client: Client, user_ids: list[int]) -> dict[int, float]:
    if not user_ids:
        return {}
    id_candidates = ["user_id", "member_id", "discord_user_id", "id"]
    ts_map: dict[int, float] = {}
    for id_col in id_candidates:
        try:
            for ids in chunked(user_ids, 400):
                resp = (
                    client.table("members")
                    .select(f"{id_col},ts,trust_score,ts_score,trust")
                    .in_(id_col, ids)
                    .execute()
                )
                for row in resp.data or []:
                    uid = as_int(row.get(id_col))
                    if uid == 0:
                        continue
                    ts = as_float(
                        row.get("ts")
                        or row.get("trust_score")
                        or row.get("ts_score")
                        or row.get("trust")
                        or DEFAULT_TS
                    )
                    ts_map[uid] = max(0.0, min(100.0, ts))
            if ts_map:
                return ts_map
        except Exception:
            continue
    return ts_map


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


def normalize_channel_name(name: str | None, channel_id: Any) -> str:
    if name and str(name).strip():
        return str(name)
    return f"channel-{channel_id}"


def channel_weight(channel_name: str) -> float:
    lower = channel_name.lower()
    if contains_any(lower, PROJECT_CHANNEL_HINTS) or contains_any(lower, KNOWLEDGE_CHANNEL_HINTS):
        return 1.2
    if contains_any(lower, HOBBY_CHANNEL_HINTS):
        return 0.8
    return 1.0


def classify_message(content: Any, channel_name: str) -> str:
    text = str(content or "").strip()
    if not text:
        return "MISC"
    if URL_RE.search(text):
        return "INFO"
    if contains_any(channel_name, OPS_CHANNEL_HINTS):
        return "OPS"
    meaningful = NON_WORD_RE.sub("", text)
    if len(meaningful) < 5:
        return "VIBE"
    if len(text) > 200:
        return "INSIGHT"
    return "MISC"


def calc_vp(effective_cp_total: float) -> int:
    if effective_cp_total <= 0:
        return 1
    vp = int(math.floor(math.log2(effective_cp_total + 1.0)) + 1)
    return max(1, min(MAX_VP, vp))


def build_core_model(
    client: Client,
    trend_days: int,
    lookback_days: int,
    max_messages: int,
    max_reactions: int,
    max_users: int,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    scan_days = max(30, trend_days, lookback_days)
    since_dt = now - timedelta(days=scan_days)

    messages = fetch_rows_window(
        client,
        "messages",
        "message_id,user_id,channel_id,content,timestamp,created_at",
        "timestamp",
        since_dt,
        max_messages,
    )
    reactions = fetch_rows_window(
        client,
        "reactions",
        "message_id,user_id,created_at,weight",
        "created_at",
        since_dt,
        max_reactions,
    )
    channels, _ = try_fetch_all_rows(client, "channels", "channel_id,name,type")

    # Track only active users in the scan scope to avoid full-table user fetch.
    seen_user_ids: list[int] = []
    seen_user_set: set[int] = set()
    for row in messages:
        uid = as_int(row.get("user_id"))
        if uid and uid not in seen_user_set:
            seen_user_set.add(uid)
            seen_user_ids.append(uid)
    for row in reactions:
        uid = as_int(row.get("user_id"))
        if uid and uid not in seen_user_set:
            seen_user_set.add(uid)
            seen_user_ids.append(uid)

    if max_users > 0 and len(seen_user_ids) > max_users:
        keep = set(seen_user_ids[:max_users])
        messages = [m for m in messages if as_int(m.get("user_id")) in keep]
        reactions = [r for r in reactions if as_int(r.get("user_id")) in keep]
        seen_user_ids = seen_user_ids[:max_users]
    users = fetch_users_by_ids(client, seen_user_ids)
    member_ts_by_user = fetch_members_ts_by_ids(client, seen_user_ids)

    day_30_ago = (now - timedelta(days=30)).date()
    day_7_ago = (now - timedelta(days=7)).date()
    trend_start = (now - timedelta(days=max(1, trend_days) - 1)).date()

    channel_name_by_id: dict[int, str] = {}
    for channel in channels:
        channel_id = as_int(channel.get("channel_id"))
        channel_name_by_id[channel_id] = normalize_channel_name(channel.get("name"), channel_id)

    user_stats: dict[int, dict[str, Any]] = {}

    def ensure_user(uid: int, username: str | None = None) -> dict[str, Any]:
        if uid not in user_stats:
            ts = member_ts_by_user.get(uid, DEFAULT_TS)
            user_stats[uid] = {
                "user_id": uid,
                "username": username or f"user-{uid}",
                "ts": ts,
                "raw_cp_total": 0.0,
                "raw_cp_30d": 0.0,
                "msg_count_total": 0,
                "msg_count_30d": 0,
                "reaction_given_total": 0,
                "reaction_given_30d": 0,
                "category_counts": {cat: 0 for cat in CATEGORY_ORDER},
                "category_cp": {cat: 0.0 for cat in CATEGORY_ORDER},
                "category_cp_30d": {cat: 0.0 for cat in CATEGORY_ORDER},
                "daily_cp": defaultdict(float),
                "activity_days": set(),
                "rank_30d": 0,
                "rank_total": 0,
            }
        elif username and user_stats[uid]["username"].startswith("user-"):
            user_stats[uid]["username"] = username
        return user_stats[uid]

    for user in users:
        uid = as_int(user.get("user_id"))
        if uid == 0:
            continue
        ensure_user(uid, str(user.get("username") or f"user-{uid}"))

    message_owner: dict[int, int] = {}
    channel_stats: dict[int, dict[str, Any]] = {}
    channel_user_cp: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    category_totals = {
        cat: {"count": 0, "raw_cp": 0.0, "raw_cp_30d": 0.0} for cat in CATEGORY_ORDER
    }
    daily_total_cp: dict[Any, float] = defaultdict(float)
    daily_total_messages: dict[Any, int] = defaultdict(int)
    daily_active_users: dict[Any, set[int]] = defaultdict(set)
    heatmap_messages: dict[tuple[int, int], int] = defaultdict(int)
    heatmap_cp: dict[tuple[int, int], float] = defaultdict(float)

    for message in messages:
        uid = as_int(message.get("user_id"))
        mid = as_int(message.get("message_id"))
        channel_id = as_int(message.get("channel_id"))
        if uid == 0 or mid == 0:
            continue
        user = ensure_user(uid)
        ts = parse_dt(message.get("timestamp") or message.get("created_at"))
        if ts is None:
            continue
        day = ts.date()
        channel_name = channel_name_by_id.get(channel_id, f"channel-{channel_id}")
        category = classify_message(message.get("content"), channel_name)
        base_cp = CATEGORY_CP[category]
        weight = channel_weight(channel_name)
        raw_cp = base_cp * weight

        user["raw_cp_total"] += raw_cp
        user["msg_count_total"] += 1
        user["category_counts"][category] += 1
        user["category_cp"][category] += raw_cp
        user["daily_cp"][day] += raw_cp
        user["activity_days"].add(day)

        if day >= day_30_ago:
            user["raw_cp_30d"] += raw_cp
            user["msg_count_30d"] += 1
            user["category_cp_30d"][category] += raw_cp

        category_totals[category]["count"] += 1
        category_totals[category]["raw_cp"] += raw_cp
        if day >= day_30_ago:
            category_totals[category]["raw_cp_30d"] += raw_cp

        if day >= trend_start:
            daily_total_cp[day] += raw_cp
            daily_total_messages[day] += 1
            daily_active_users[day].add(uid)

        key = (ts.weekday(), ts.hour)  # Monday=0
        heatmap_messages[key] += 1
        heatmap_cp[key] += raw_cp

        message_owner[mid] = uid

        if channel_id not in channel_stats:
            channel_stats[channel_id] = {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "weight": weight,
                "messages_30d": 0,
                "raw_cp_30d": 0.0,
                "active_users_30d": set(),
            }
        if day >= day_30_ago:
            channel_stats[channel_id]["messages_30d"] += 1
            channel_stats[channel_id]["raw_cp_30d"] += raw_cp
            channel_stats[channel_id]["active_users_30d"].add(uid)
            channel_user_cp[channel_id][uid] += raw_cp

    edge_weights: dict[tuple[int, int], float] = defaultdict(float)
    for reaction in reactions:
        reactor_id = as_int(reaction.get("user_id"))
        message_id = as_int(reaction.get("message_id"))
        if reactor_id == 0:
            continue
        reactor = ensure_user(reactor_id)
        ts = parse_dt(reaction.get("created_at"))
        if ts is None:
            continue
        day = ts.date()
        raw_cp = REACTION_GIVE_CP

        reactor["raw_cp_total"] += raw_cp
        reactor["reaction_given_total"] += 1
        reactor["daily_cp"][day] += raw_cp
        reactor["activity_days"].add(day)
        if day >= day_30_ago:
            reactor["raw_cp_30d"] += raw_cp
            reactor["reaction_given_30d"] += 1

        if day >= trend_start:
            daily_total_cp[day] += raw_cp
            daily_active_users[day].add(reactor_id)

        target_id = message_owner.get(message_id)
        if target_id and target_id != reactor_id:
            edge_weights[(reactor_id, target_id)] += 1.0

    for uid, stats in user_stats.items():
        ts = max(0.0, min(100.0, as_float(stats["ts"])))
        stats["ts"] = ts
        stats["effective_cp_total"] = stats["raw_cp_total"] * (ts / 100.0)
        stats["effective_cp_30d"] = stats["raw_cp_30d"] * (ts / 100.0)
        vp = calc_vp(stats["effective_cp_total"])
        stats["vp"] = vp
        stats["effective_vp"] = max(1, int(math.floor(vp * (ts / 100.0))))

        days = sorted(stats["activity_days"])
        stats["current_streak"] = 0
        stats["longest_streak"] = 0
        if days:
            longest = 1
            run = 1
            for i in range(1, len(days)):
                if days[i] == days[i - 1] + timedelta(days=1):
                    run += 1
                else:
                    run = 1
                longest = max(longest, run)
            stats["longest_streak"] = longest

            cursor = now.date()
            streak = 0
            day_set = stats["activity_days"]
            while cursor in day_set:
                streak += 1
                cursor -= timedelta(days=1)
            stats["current_streak"] = streak

    ranked_30d = sorted(
        user_stats.values(), key=lambda u: (u["effective_cp_30d"], u["raw_cp_30d"]), reverse=True
    )
    ranked_total = sorted(
        user_stats.values(), key=lambda u: (u["effective_cp_total"], u["raw_cp_total"]), reverse=True
    )
    for i, row in enumerate(ranked_30d, start=1):
        row["rank_30d"] = i
    for i, row in enumerate(ranked_total, start=1):
        row["rank_total"] = i

    channel_rows: list[dict[str, Any]] = []
    for channel_id, row in channel_stats.items():
        leaders = sorted(channel_user_cp[channel_id].items(), key=lambda kv: kv[1], reverse=True)
        champ_user_id = leaders[0][0] if leaders else 0
        champ_cp = leaders[0][1] if leaders else 0.0
        champ_name = user_stats.get(champ_user_id, {}).get("username", "-")
        channel_rows.append(
            {
                "channel_id": channel_id,
                "channel_name": row["channel_name"],
                "weight": row["weight"],
                "messages_30d": row["messages_30d"],
                "raw_cp_30d": row["raw_cp_30d"],
                "active_users_30d": len(row["active_users_30d"]),
                "champ_user_id": champ_user_id,
                "champ_name": champ_name,
                "champ_cp_30d": champ_cp,
            }
        )
    channel_rows.sort(key=lambda x: x["raw_cp_30d"], reverse=True)

    top_edges = sorted(edge_weights.items(), key=lambda kv: kv[1], reverse=True)
    node_degree: dict[int, float] = defaultdict(float)
    for (source, target), weight in top_edges:
        node_degree[source] += weight
        node_degree[target] += weight
    top_nodes = sorted(node_degree.items(), key=lambda kv: kv[1], reverse=True)

    category_leaderboards: dict[str, list[tuple[str, int, float]]] = {}
    for category in CATEGORY_ORDER:
        rows: list[tuple[str, int, float]] = []
        for u in user_stats.values():
            count = as_int(u["category_counts"][category])
            cp = as_float(u["category_cp_30d"][category])
            if count <= 0 and cp <= 0:
                continue
            rows.append((u["username"], count, cp))
        rows.sort(key=lambda t: t[2], reverse=True)
        category_leaderboards[category] = rows

    model = {
        "generated_at": now,
        "scan_days": scan_days,
        "scan_since": since_dt,
        "users_count": len(user_stats),
        "messages_count": len(messages),
        "reactions_count": len(reactions),
        "stats_by_user": user_stats,
        "ranked_30d": ranked_30d,
        "ranked_total": ranked_total,
        "category_totals": category_totals,
        "category_leaderboards": category_leaderboards,
        "channel_rows": channel_rows,
        "daily_total_cp": daily_total_cp,
        "daily_total_messages": daily_total_messages,
        "daily_active_users": daily_active_users,
        "heatmap_messages": heatmap_messages,
        "heatmap_cp": heatmap_cp,
        "top_edges": top_edges,
        "top_nodes": top_nodes,
        "day_7_ago": day_7_ago,
        "day_30_ago": day_30_ago,
    }
    return model


def resolve_focus_user(model: dict[str, Any], selector: str) -> dict[str, Any] | None:
    ranked = model["ranked_30d"]
    if not ranked:
        return None
    if not selector:
        return ranked[0]

    by_user = model["stats_by_user"]
    if selector.isdigit():
        return by_user.get(int(selector))

    selector_l = selector.lower()
    exact = [u for u in by_user.values() if str(u["username"]).lower() == selector_l]
    if exact:
        return exact[0]
    partial = [u for u in by_user.values() if selector_l in str(u["username"]).lower()]
    if partial:
        partial.sort(key=lambda u: u["effective_cp_30d"], reverse=True)
        return partial[0]
    return ranked[0]


def lines_overview(model: dict[str, Any], days: int, width: int) -> list[str]:
    ranked_30d = model["ranked_30d"]
    users_count = model["users_count"]
    messages_count = model["messages_count"]
    reactions_count = model["reactions_count"]

    total_raw_30d = sum(as_float(u["raw_cp_30d"]) for u in ranked_30d)
    total_eff_30d = sum(as_float(u["effective_cp_30d"]) for u in ranked_30d)
    avg_ts = (
        sum(as_float(u["ts"]) for u in ranked_30d) / len(ranked_30d) if ranked_30d else DEFAULT_TS
    )
    avg_vp = sum(as_float(u["vp"]) for u in ranked_30d) / len(ranked_30d) if ranked_30d else 1.0

    scan_days = as_int(model.get("scan_days", 0))
    lines = [
        "v2 model: category CP + channel weight + TS multiplier + VP derivation",
        f"Scan scope: last {scan_days}d",
        f"Members: {users_count} | Messages: {messages_count} | Reactions: {reactions_count}",
        f"30d RawCP: {total_raw_30d:,.1f} | 30d EffectiveCP: {total_eff_30d:,.1f}",
        f"Avg TS: {avg_ts:.1f} | Avg VP: {avg_vp:.2f}",
        "",
        "Category Mix (30d Effective RawCP base)",
    ]

    category_rows: list[list[Any]] = []
    total_cat_cp = sum(as_float(model["category_totals"][c]["raw_cp_30d"]) for c in CATEGORY_ORDER)
    for cat in CATEGORY_ORDER:
        cat_cp = as_float(model["category_totals"][cat]["raw_cp_30d"])
        cat_count = as_int(model["category_totals"][cat]["count"])
        share = (cat_cp / total_cat_cp * 100.0) if total_cat_cp > 0 else 0.0
        category_rows.append([cat, cat_count, f"{cat_cp:.1f}", f"{share:.1f}%"])
    lines.extend(render_table_lines(["Cat", "Msgs", "RawCP30d", "Share"], category_rows, width))

    lines.append("")
    lines.append(f"CP Trend ({max(1, days)} days)")

    today = datetime.now(timezone.utc).date()
    days_list = [today - timedelta(days=i) for i in range(max(1, days) - 1, -1, -1)]
    cp_series = model["daily_total_cp"]
    max_cp = max((as_float(cp_series.get(d, 0.0)) for d in days_list), default=1.0)
    bar_width = max(8, min(42, width - 28))
    for day in days_list:
        cp = as_float(cp_series.get(day, 0.0))
        messages = as_int(model["daily_total_messages"].get(day, 0))
        active = len(model["daily_active_users"].get(day, set()))
        unit = int((cp / max_cp) * bar_width) if max_cp > 0 else 0
        bar = "#" * max(unit, 1 if cp > 0 else 0)
        lines.append(clip(f"{day} | {bar:<{bar_width}} CP:{cp:6.1f} msg:{messages:4d} u:{active:3d}", width))

    if ranked_30d:
        lines.append("")
        top = ranked_30d[0]
        lines.append(
            f"Top Momentum (30d): {top['username']} | EffCP {top['effective_cp_30d']:.1f} | TS {top['ts']:.0f} | VP {top['vp']}"
        )
    return lines


def lines_mystats(model: dict[str, Any], selector: str, width: int) -> list[str]:
    user = resolve_focus_user(model, selector)
    if user is None:
        return ["(no user data)"]

    lines = [
        f"User: {user['username']} (id={user['user_id']})",
        f"Rank 30d: #{user['rank_30d']} | Rank Total: #{user['rank_total']}",
        f"RawCP Scope: {user['raw_cp_total']:.1f} | EffectiveCP Scope: {user['effective_cp_total']:.1f}",
        f"RawCP 30d:  {user['raw_cp_30d']:.1f} | EffectiveCP 30d:  {user['effective_cp_30d']:.1f}",
        f"TS: {user['ts']:.1f} | VP: {user['vp']} | EffectiveVP: {user['effective_vp']}",
        f"Messages 30d: {user['msg_count_30d']} | Reactions Given 30d: {user['reaction_given_30d']}",
        f"Streak: current {user['current_streak']}d / longest {user['longest_streak']}d",
        "",
        "Category Breakdown (30d)",
    ]

    total_cat_cp = sum(as_float(user["category_cp_30d"][c]) for c in CATEGORY_ORDER)
    rows: list[list[Any]] = []
    for cat in CATEGORY_ORDER:
        cp = as_float(user["category_cp_30d"][cat])
        count = as_int(user["category_counts"][cat])
        share = (cp / total_cat_cp * 100.0) if total_cat_cp > 0 else 0.0
        rows.append([cat, count, f"{cp:.1f}", f"{share:.1f}%"])
    lines.extend(render_table_lines(["Cat", "Msgs", "RawCP30d", "Share"], rows, width))

    lines.append("")
    lines.append("Recent 7d CP")
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    values = [as_float(user["daily_cp"].get(d, 0.0)) for d in days]
    max_cp = max(values) if values else 1.0
    bar_width = max(8, min(35, width - 25))
    for d, cp in zip(days, values):
        unit = int((cp / max_cp) * bar_width) if max_cp > 0 else 0
        bar = "#" * max(unit, 1 if cp > 0 else 0)
        lines.append(clip(f"{d} | {bar:<{bar_width}} {cp:6.1f}", width))
    return lines


def lines_leaderboard(model: dict[str, Any], limit: int, width: int) -> list[str]:
    rows: list[list[Any]] = []
    for i, u in enumerate(model["ranked_30d"][:limit], start=1):
        rows.append(
            [
                i,
                u["username"],
                f"{u['effective_cp_30d']:.1f}",
                f"{u['raw_cp_30d']:.1f}",
                f"{u['ts']:.0f}",
                u["vp"],
                u["current_streak"],
            ]
        )
    lines = ["Monthly CP Leaderboard (30d, v2 model)"]
    lines.extend(
        render_table_lines(
            ["Rank", "User", "EffCP30d", "RawCP30d", "TS", "VP", "Streak"],
            rows,
            width,
        )
    )
    return lines


def lines_categories(model: dict[str, Any], limit: int, width: int) -> list[str]:
    lines: list[str] = ["Category Leaderboards (30d RawCP by category)"]
    for cat in CATEGORY_ORDER:
        lines.append("")
        lines.append(f"[{cat}]")
        rows = []
        for i, (name, count, cp) in enumerate(model["category_leaderboards"][cat][:limit], start=1):
            rows.append([i, name, count, f"{cp:.1f}"])
        lines.extend(render_table_lines(["Rank", "User", "Msgs", "RawCP30d"], rows, width))
    return lines


def lines_channels(model: dict[str, Any], limit: int, width: int) -> list[str]:
    rows = []
    for i, ch in enumerate(model["channel_rows"][:limit], start=1):
        rows.append(
            [
                i,
                ch["channel_name"],
                f"x{ch['weight']:.1f}",
                ch["messages_30d"],
                ch["active_users_30d"],
                f"{ch['raw_cp_30d']:.1f}",
                f"{ch['champ_name']} ({ch['champ_cp_30d']:.1f})",
            ]
        )
    lines = [
        "Channel Ranking (30d)",
        "Champion is top CP contributor per channel (v2 monthly concept).",
    ]
    lines.extend(
        render_table_lines(
            ["Rank", "Channel", "Coef", "Msgs", "Active", "RawCP30d", "Champion(cp)"],
            rows,
            width,
        )
    )
    return lines


def lines_behavior(model: dict[str, Any], width: int) -> list[str]:
    heatmap_messages = model["heatmap_messages"]
    max_count = max((as_int(v) for v in heatmap_messages.values()), default=0)
    levels = " .:-=+*#%@"

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    lines = ["Activity Heatmap (message count)", "Hours: 012345678901234567890123"]
    for day in range(7):
        chars: list[str] = []
        for hour in range(24):
            count = as_int(heatmap_messages.get((day, hour), 0))
            idx = 0 if max_count <= 0 else int((count / max_count) * (len(levels) - 1))
            chars.append(levels[idx])
        lines.append(f"{day_names[day]}: {''.join(chars)}")
    lines.append("Legend: low=' ' high='@'")

    busiest = sorted(heatmap_messages.items(), key=lambda kv: kv[1], reverse=True)[:5]
    if busiest:
        lines.append("")
        lines.append("Top Time Slots")
        rows = []
        for (day, hour), count in busiest:
            rows.append([day_names[day], f"{hour:02d}:00", count])
        lines.extend(render_table_lines(["Day", "Hour", "Messages"], rows, width))
    return [clip(line, width) for line in lines]


def lines_graph(model: dict[str, Any], limit: int, width: int) -> list[str]:
    user_map = model["stats_by_user"]
    edge_rows: list[list[Any]] = []
    for (source_id, target_id), weight in model["top_edges"][:limit]:
        source = user_map.get(source_id, {}).get("username", f"user-{source_id}")
        target = user_map.get(target_id, {}).get("username", f"user-{target_id}")
        edge_rows.append([source, target, int(weight)])

    node_rows: list[list[Any]] = []
    for user_id, degree in model["top_nodes"][:limit]:
        name = user_map.get(user_id, {}).get("username", f"user-{user_id}")
        node_rows.append([name, f"{degree:.0f}"])

    lines = ["Social Graph (reactions: source -> target)"]
    lines.extend(render_table_lines(["From", "To", "Weight"], edge_rows, width))
    lines.append("")
    lines.append("Top Connected Users")
    lines.extend(render_table_lines(["User", "WeightedDegree"], node_rows, width))
    return lines


def lines_governance(model: dict[str, Any], limit: int, width: int) -> list[str]:
    ranked_total = model["ranked_total"]
    vp_dist: dict[int, int] = defaultdict(int)
    total_eff = 0.0
    for user in ranked_total:
        vp_dist[as_int(user["vp"])] += 1
        total_eff += as_float(user["effective_cp_total"])

    top_n = min(limit, len(ranked_total))
    top_eff = sum(as_float(u["effective_cp_total"]) for u in ranked_total[:top_n])
    share = (top_eff / total_eff * 100.0) if total_eff > 0 else 0.0

    lines = [
        "Governance View (VP from scoped effective CP)",
        f"VP formula: floor(log2(effective_cp + 1)) + 1, cap {MAX_VP}",
        f"Power concentration: top {top_n} share = {share:.1f}%",
        "",
        "VP Distribution",
    ]

    dist_rows = [[vp, vp_dist.get(vp, 0)] for vp in range(1, MAX_VP + 1)]
    lines.extend(render_table_lines(["VP", "Members"], dist_rows, width))
    lines.append("")
    lines.append("Top Governance Weights")

    top_rows = []
    for i, user in enumerate(ranked_total[:limit], start=1):
        top_rows.append(
            [
                i,
                user["username"],
                f"{user['effective_cp_total']:.1f}",
                f"{user['ts']:.0f}",
                user["vp"],
                user["effective_vp"],
            ]
        )
    lines.extend(
        render_table_lines(
            ["Rank", "User", "EffCP Total", "TS", "VP", "EffVP"],
            top_rows,
            width,
        )
    )
    return lines


def fetch_operations_status(client: Client) -> dict[str, Any]:
    status: dict[str, Any] = {}
    for table in DESIGN_TABLES:
        try:
            resp = client.table(table).select("*").limit(1).execute()
            status[table] = {
                "available": True,
                "sample_count": len(resp.data or []),
                "error": None,
            }
        except Exception as exc:
            status[table] = {"available": False, "sample_count": 0, "error": str(exc)}
    return status


def lines_operations(status: dict[str, Any], width: int) -> list[str]:
    rows = []
    for table in DESIGN_TABLES:
        row = status.get(table, {})
        available = bool(row.get("available"))
        rows.append([table, "READY" if available else "MISSING", row.get("sample_count", 0)])
    lines = [
        "Phase Readiness (design v2 tables)",
        "READY = table exists, MISSING = not migrated yet",
    ]
    lines.extend(render_table_lines(["Table", "Status", "Rows(sampled)"], rows, width))

    lines.append("")
    lines.append("Command Readiness")
    command_rows = [
        ["/mystats", "READY", "derived from users/messages/reactions"],
        ["/leaderboard", "READY", "30d CP ranking"],
        ["/leaderboard category", "READY", "category leaderboard"],
        ["/history", "PARTIAL", "derived daily history, cp_ledger not ready"],
        [
            "/mytitles /settitle",
            "READY"
            if status.get("achievements", {}).get("available")
            and status.get("member_achievements", {}).get("available")
            else "PENDING",
            "requires achievements tables",
        ],
        [
            "/vote create /vote list",
            "READY" if status.get("votes", {}).get("available") else "PENDING",
            "requires votes tables",
        ],
        [
            "/issue create /issue list",
            "READY" if status.get("issues", {}).get("available") else "PENDING",
            "requires issues table",
        ],
        [
            "/quest create",
            "READY" if status.get("quests", {}).get("available") else "PENDING",
            "requires quests table",
        ],
        ["/dispute", "PENDING", "review/dispute schema not found in current DB"],
    ]
    lines.extend(render_table_lines(["Command", "Status", "Backend"], command_rows, width))
    return lines


class DashboardTUI:
    def __init__(
        self,
        client: Client,
        limit: int,
        days: int,
        refresh: float,
        focus_user: str,
        lookback_days: int,
        max_messages: int,
        max_reactions: int,
        max_users: int,
    ) -> None:
        self.client = client
        self.limit = max(1, limit)
        self.days = max(1, days)
        self.refresh_interval = max(5.0, refresh)
        self.focus_user = focus_user
        self.lookback_days = max(30, lookback_days)
        self.max_messages = max(1000, max_messages)
        self.max_reactions = max(1000, max_reactions)
        self.max_users = max(100, max_users)
        self.page_idx = 0
        self.auto_refresh = True
        self.cache: dict[str, Any] = {}
        self.last_refresh_at: datetime | None = None
        self.last_error: str | None = None

    @property
    def current_page(self) -> str:
        return PAGE_ORDER[self.page_idx]

    def refresh_current_page(self) -> None:
        self.last_error = None
        page = self.current_page
        try:
            if page == "operations":
                self.cache["operations"] = fetch_operations_status(self.client)
            else:
                self.cache["core"] = build_core_model(
                    self.client,
                    self.days,
                    self.lookback_days,
                    self.max_messages,
                    self.max_reactions,
                    self.max_users,
                )
            self.last_refresh_at = datetime.now()
        except Exception as exc:
            self.last_error = str(exc)

    def render_page_lines(self, width: int) -> list[str]:
        page = self.current_page
        if page == "operations":
            status = self.cache.get("operations")
            if status is None:
                return ["Loading operations status..."]
            return lines_operations(status, width)

        model = self.cache.get("core")
        if model is None:
            return ["Loading core model..."]

        if page == "overview":
            return lines_overview(model, self.days, width)
        if page == "mystats":
            return lines_mystats(model, self.focus_user, width)
        if page == "leaderboard":
            return lines_leaderboard(model, self.limit, width)
        if page == "categories":
            return lines_categories(model, self.limit, width)
        if page == "channels":
            return lines_channels(model, self.limit, width)
        if page == "behavior":
            return lines_behavior(model, width)
        if page == "graph":
            return lines_graph(model, self.limit, width)
        if page == "governance":
            return lines_governance(model, self.limit, width)
        return ["Unknown page"]

    def draw(self, stdscr: Any) -> None:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        title = f"comm0ns dashboard v2 | {PAGE_TITLES[self.current_page]} ({self.page_idx + 1}/{len(PAGE_ORDER)})"
        status = (
            f"limit={self.limit} days={self.days} lookback={self.lookback_days}d "
            f"refresh={self.refresh_interval:.0f}s auto={'on' if self.auto_refresh else 'off'}"
        )
        stdscr.addnstr(0, 0, clip(f"{title} | {status}", width), width)

        tabs = " ".join(
            f"[{i + 1}:{PAGE_TITLES[p]}]" if i != self.page_idx else f"*{i + 1}:{PAGE_TITLES[p]}*"
            for i, p in enumerate(PAGE_ORDER)
        )
        stdscr.addnstr(1, 0, clip(tabs, width), width)
        help_line = "q:quit tab/arrow:page r:refresh a:auto +/-:limit [ ]:days u:focus auto-top"
        stdscr.addnstr(2, 0, clip(help_line, width), width)
        stdscr.hline(3, 0, "-", width)

        lines = self.render_page_lines(max(1, width - 1))
        body_height = max(0, height - 6)
        for i in range(min(body_height, len(lines))):
            stdscr.addnstr(4 + i, 0, clip(lines[i], width), width)

        updated = self.last_refresh_at.strftime("%H:%M:%S") if self.last_refresh_at else "never"
        footer = f"updated: {updated} | focus_user={self.focus_user or 'auto-top'}"
        if self.last_error:
            footer += f" | error: {self.last_error}"
        stdscr.hline(height - 2, 0, "-", width)
        stdscr.addnstr(height - 1, 0, clip(footer, width), width)
        stdscr.refresh()

    def handle_key(self, key: int) -> bool:
        if key in (ord("q"), ord("Q")):
            return False
        if key in (9, curses.KEY_RIGHT):
            self.page_idx = (self.page_idx + 1) % len(PAGE_ORDER)
            self.refresh_current_page()
        elif key == curses.KEY_LEFT:
            self.page_idx = (self.page_idx - 1) % len(PAGE_ORDER)
            self.refresh_current_page()
        elif ord("1") <= key <= ord("9"):
            idx = key - ord("1")
            if idx < len(PAGE_ORDER):
                self.page_idx = idx
                self.refresh_current_page()
        elif key in (ord("r"), ord("R")):
            self.refresh_current_page()
        elif key == ord("a"):
            self.auto_refresh = not self.auto_refresh
        elif key == ord("+"):
            self.limit += 5
            self.refresh_current_page()
        elif key == ord("-"):
            self.limit = max(5, self.limit - 5)
            self.refresh_current_page()
        elif key == ord("]"):
            self.days += 7
            self.refresh_current_page()
        elif key == ord("["):
            self.days = max(7, self.days - 7)
            self.refresh_current_page()
        elif key == ord("u"):
            self.focus_user = ""
            self.refresh_current_page()
        return True

    def run(self, stdscr: Any) -> None:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(200)
        self.refresh_current_page()
        last_tick = time.monotonic()
        running = True

        while running:
            now = time.monotonic()
            if self.auto_refresh and (now - last_tick) >= self.refresh_interval:
                self.refresh_current_page()
                last_tick = now

            self.draw(stdscr)
            key = stdscr.getch()
            if key != -1:
                running = self.handle_key(key)
                last_tick = now


def print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def run_non_tui(
    client: Client,
    section: str,
    limit: int,
    days: int,
    focus_user: str,
    lookback_days: int,
    max_messages: int,
    max_reactions: int,
    max_users: int,
) -> int:
    try:
        if section == "operations":
            print("\nOperations\n==========")
            print_lines(lines_operations(fetch_operations_status(client), 120))
            return 0

        model = build_core_model(
            client,
            days,
            lookback_days,
            max_messages,
            max_reactions,
            max_users,
        )
        sections = PAGE_ORDER if section == "all" else [section]

        for page in sections:
            print()
            print(f"{PAGE_TITLES[page]}")
            print("=" * len(PAGE_TITLES[page]))
            if page == "overview":
                print_lines(lines_overview(model, days, 120))
            elif page == "mystats":
                print_lines(lines_mystats(model, focus_user, 120))
            elif page == "leaderboard":
                print_lines(lines_leaderboard(model, limit, 120))
            elif page == "categories":
                print_lines(lines_categories(model, limit, 120))
            elif page == "channels":
                print_lines(lines_channels(model, limit, 120))
            elif page == "behavior":
                print_lines(lines_behavior(model, 120))
            elif page == "graph":
                print_lines(lines_graph(model, limit, 120))
            elif page == "governance":
                print_lines(lines_governance(model, limit, 120))
            elif page == "operations":
                print_lines(lines_operations(fetch_operations_status(client), 120))
        return 0
    except Exception as exc:
        print(f"Error: failed to render dashboard: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    args = parse_args()
    if args.tui and not args.skip_auth:
        try:
            session = ensure_tui_auth_session(
                force_login=bool(args.force_login),
                timeout_sec=max(30, int(args.auth_timeout)),
            )
            user = session.get("user", {}) if isinstance(session.get("user"), dict) else {}
            user_id = str(user.get("id") or "").strip()
            email = str(user.get("email") or "").strip()
            user_name = str((user.get("user_metadata") or {}).get("full_name") or "").strip()
            display = email or user_name or user_id or "unknown user"
            print(f"Authenticated: {display}")
        except AuthError as exc:
            print(f"Error: authentication failed: {exc}", file=sys.stderr)
            sys.exit(1)

    client = get_client(args.timeout)

    if args.tui:
        try:
            app = DashboardTUI(
                client,
                args.limit,
                args.days,
                args.refresh,
                args.user.strip(),
                args.lookback_days,
                args.max_messages,
                args.max_reactions,
                args.max_users,
            )
            curses.wrapper(app.run)
        except KeyboardInterrupt:
            print()
            sys.exit(130)
        except Exception as exc:
            print(f"Error: failed to start TUI: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        code = run_non_tui(
            client,
            args.section,
            args.limit,
            args.days,
            args.user.strip(),
            args.lookback_days,
            args.max_messages,
            args.max_reactions,
            args.max_users,
        )
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    sys.exit(code)


if __name__ == "__main__":
    main()
