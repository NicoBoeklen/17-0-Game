"""
Live NFL 2026/2027 Season Data Synchronizer.
Fetches live 2026/2027 rosters, depth charts, standings, and 2026 regular season
player stats from ESPN NFL API & Sleeper API, computes exact per-position rankings
(#1, #2, #3... per position), and saves to backend/data/nfl_live_data.json.
"""
import concurrent.futures
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).parent / "data"
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
BUNDLED_CACHE_FILE = DATA_DIR / "nfl_live_data.json"
TMP_CACHE_FILE = Path(tempfile.gettempdir()) / "nfl_live_data.json"
CACHE_FILE = BUNDLED_CACHE_FILE


def get_readable_cache_file() -> Path:
    if os.environ.get("VERCEL") and TMP_CACHE_FILE.exists():
        return TMP_CACHE_FILE
    if BUNDLED_CACHE_FILE.exists():
        return BUNDLED_CACHE_FILE
    return TMP_CACHE_FILE


def write_cache_json(payload: Dict[str, Any]) -> Path:
    target = TMP_CACHE_FILE if os.environ.get("VERCEL") else BUNDLED_CACHE_FILE
    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return target
    except OSError:
        with open(TMP_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return TMP_CACHE_FILE

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=32"
ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"
ESPN_TEAM_DETAIL_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}"
ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"
ESPN_DEPTH_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/depthcharts"
SLEEPER_STATE_URL = "https://api.sleeper.app/v1/state/nfl"
SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
SLEEPER_STATS_URL = "https://api.sleeper.app/v1/stats/nfl/regular/{season}"

# 2026/2027 NFL Head Coaches (Fallback if ESPN coach endpoint omits name)
COACHES_2026: Dict[str, str] = {
    "ARI": "Jonathan Gannon",
    "ATL": "Raheem Morris",
    "BAL": "John Harbaugh",
    "BUF": "Sean McDermott",
    "CAR": "Dave Canales",
    "CHI": "Ben Johnson",
    "CIN": "Zac Taylor",
    "CLE": "Kevin Stefanski",
    "DAL": "Brian Schottenheimer",
    "DEN": "Sean Payton",
    "DET": "Dan Campbell",
    "GB": "Matt LaFleur",
    "HOU": "DeMeco Ryans",
    "IND": "Shane Steichen",
    "JAX": "Liam Coen",
    "KC": "Andy Reid",
    "LAC": "Jim Harbaugh",
    "LAR": "Sean McVay",
    "LV": "Pete Carroll",
    "MIA": "Mike McDaniel",
    "MIN": "Kevin O'Connell",
    "NE": "Mike Vrabel",
    "NO": "Kellen Moore",
    "NYG": "Brian Daboll",
    "NYJ": "Aaron Glenn",
    "PHI": "Nick Sirianni",
    "PIT": "Mike Tomlin",
    "SEA": "Mike Macdonald",
    "SF": "Kyle Shanahan",
    "TB": "Todd Bowles",
    "TEN": "Brian Callahan",
    "WAS": "Dan Quinn",
}

ABBR_MAP = {
    "WSH": "WAS",
    "JAC": "JAX",
}

# NFL Trench Pass-Block Win Rate (PBWR %) & Sack-Rate (%) Baselines per OL Unit
# Used alongside live RB Rushing YPC / Rush YPG & QB Sack Rate (zero dependency on team PPG!)
OL_TRENCH_BASELINES: Dict[str, Dict[str, float]] = {
    "DET": {"pbwr": 72.5, "sack_rate": 4.1, "ypc_base": 4.9},
    "PHI": {"pbwr": 71.8, "sack_rate": 4.4, "ypc_base": 4.8},
    "DEN": {"pbwr": 70.4, "sack_rate": 4.6, "ypc_base": 4.5},
    "TB":  {"pbwr": 69.5, "sack_rate": 4.8, "ypc_base": 4.8},
    "BUF": {"pbwr": 69.2, "sack_rate": 3.9, "ypc_base": 4.6},
    "GB":  {"pbwr": 68.8, "sack_rate": 4.5, "ypc_base": 4.6},
    "ALT": {"pbwr": 68.0, "sack_rate": 5.0, "ypc_base": 4.7},
    "ATL": {"pbwr": 68.4, "sack_rate": 4.9, "ypc_base": 4.8},
    "KC":  {"pbwr": 68.1, "sack_rate": 4.7, "ypc_base": 4.6},
    "BAL": {"pbwr": 67.6, "sack_rate": 5.1, "ypc_base": 5.1},
    "MIN": {"pbwr": 66.8, "sack_rate": 5.4, "ypc_base": 4.5},
    "LAC": {"pbwr": 66.2, "sack_rate": 5.5, "ypc_base": 4.4},
    "SF":  {"pbwr": 65.8, "sack_rate": 5.6, "ypc_base": 4.6},
    "IND": {"pbwr": 65.5, "sack_rate": 5.4, "ypc_base": 4.5},
    "LAR": {"pbwr": 65.0, "sack_rate": 5.7, "ypc_base": 4.5},
    "DAL": {"pbwr": 64.5, "sack_rate": 5.8, "ypc_base": 4.5},
    "ARI": {"pbwr": 63.8, "sack_rate": 5.9, "ypc_base": 4.6},
    "WAS": {"pbwr": 63.5, "sack_rate": 6.1, "ypc_base": 4.5},
    "PIT": {"pbwr": 63.0, "sack_rate": 6.2, "ypc_base": 4.4},
    "CHI": {"pbwr": 62.4, "sack_rate": 6.5, "ypc_base": 4.5},
    "JAX": {"pbwr": 62.0, "sack_rate": 6.3, "ypc_base": 4.4},
    "NYJ": {"pbwr": 61.5, "sack_rate": 6.4, "ypc_base": 4.3},
    "CAR": {"pbwr": 61.2, "sack_rate": 6.5, "ypc_base": 4.3},
    "MIA": {"pbwr": 60.5, "sack_rate": 6.6, "ypc_base": 4.2},
    "HOU": {"pbwr": 59.4, "sack_rate": 7.2, "ypc_base": 4.1},
    "CIN": {"pbwr": 58.5, "sack_rate": 7.4, "ypc_base": 4.1},
    "LV":  {"pbwr": 58.0, "sack_rate": 7.5, "ypc_base": 4.0},
    "NO":  {"pbwr": 57.5, "sack_rate": 7.6, "ypc_base": 4.0},
    "CLE": {"pbwr": 56.8, "sack_rate": 8.1, "ypc_base": 3.9},
    "SEA": {"pbwr": 56.2, "sack_rate": 8.2, "ypc_base": 4.1},
    "NYG": {"pbwr": 55.5, "sack_rate": 8.6, "ypc_base": 4.1},
    "TEN": {"pbwr": 54.8, "sack_rate": 8.8, "ypc_base": 4.0},
    "NE":  {"pbwr": 54.2, "sack_rate": 9.1, "ypc_base": 4.0},
}


def compute_player_raw_score(p: Dict[str, Any]) -> float:
    """Unified 2026/27 positional performance score blending total production, PPG efficiency, and TDs."""
    pos = p.get("position", "")
    ppr = float(p.get("pts_ppr", 0.0) or 0.0)
    ppg = float(p.get("ppg_ppr", 0.0) or 0.0)
    gp = int(p.get("gp", 0) or 0)
    # Reliability multiplier so 1-game flukes don't outrank proven starters, while 6+ game starters get full PPG credit
    reliability = min(1.0, gp / 4.0) if gp > 0 else 0.0
    eff_ppg = ppg * reliability

    if pos == "QB":
        raw = (
            ppr * 1.0
            + eff_ppg * 5.0
            + p.get("pass_td", 0) * 2.2
            + p.get("rush_td", 0) * 2.5
            - p.get("pass_int", 0) * 1.6
        )
    elif pos == "RB":
        raw = (
            ppr * 1.0
            + eff_ppg * 4.5
            + (p.get("rush_yd", 0) + p.get("rec_yd", 0)) * 0.045
            + (p.get("rush_td", 0) + p.get("rec_td", 0)) * 2.2
        )
    elif pos == "WR":
        raw = (
            ppr * 1.0
            + eff_ppg * 4.5
            + p.get("rec_yd", 0) * 0.045
            + p.get("rec_td", 0) * 2.2
        )
    else:  # TE
        raw = (
            ppr * 1.0
            + eff_ppg * 5.0
            + p.get("rec_yd", 0) * 0.05
            + p.get("rec_td", 0) * 2.5
        )
    if p.get("stat_season") != "2026/27":
        raw *= 0.65
    return round(raw, 3)


def compute_ol_trench_metrics(abbr: str, team_players: List[Dict[str, Any]], gp: int) -> Dict[str, Any]:
    """
    Calculates OL rating strictly from Trench / Blocking metrics (Pass Protection + Run Blocking),
    completely decoupled from team Offense Points (ppg_for) and Win%.
    """
    gp_safe = max(1, gp)
    rbs = [p for p in team_players if p.get("position") == "RB"]
    qbs = [p for p in team_players if p.get("position") == "QB"]

    rb_rush_yds = sum(int(p.get("rush_yd", 0) or 0) for p in rbs)
    rb_rush_tds = sum(int(p.get("rush_td", 0) or 0) for p in rbs)
    rb_rush_att = sum(int(p.get("rush_att", 0) or 0) for p in rbs)

    qb_pass_att = sum(int(p.get("pass_att", 0) or 0) for p in qbs)
    qb_sacks = sum(int(p.get("pass_sack", 0) or 0) for p in qbs)

    base = OL_TRENCH_BASELINES.get(abbr, {"pbwr": 62.0, "sack_rate": 6.5, "ypc_base": 4.3})
    rb_rush_ypg = rb_rush_yds / gp_safe
    rb_td_pg = rb_rush_tds / gp_safe

    if rb_rush_att >= 25:
        live_ypc = rb_rush_yds / rb_rush_att
        rb_ypc = round(live_ypc * 0.65 + base["ypc_base"] * 0.35, 2)
    else:
        # Derive YPC from RB rushing yards per game & trench baseline
        est_ypc = 3.8 + min(1.5, (rb_rush_ypg / 115.0) * 0.95)
        rb_ypc = round(est_ypc * 0.55 + base["ypc_base"] * 0.45, 2)

    if qb_pass_att >= 40 and qb_sacks > 0:
        live_sack_rate = (qb_sacks / (qb_pass_att + qb_sacks)) * 100.0
        sack_rate_pct = round(live_sack_rate * 0.6 + base["sack_rate"] * 0.4, 1)
    else:
        sack_rate_pct = round(base["sack_rate"], 1)

    pbwr_pct = round(base["pbwr"], 1)

    # 50% Pass Protection (high PBWR + low Sack Rate) + 50% Run Blocking (RB YPC + RB Rush YPG + RB Rush TDs)
    pass_block_score = (pbwr_pct - 50.0) * 1.8 + (10.5 - sack_rate_pct) * 5.2
    run_block_score = (rb_ypc - 3.5) * 18.0 + (rb_rush_ypg * 0.22) + (rb_td_pg * 7.5)
    ol_score = round(pass_block_score * 0.52 + run_block_score * 0.48, 2)

    return {
        "ol_score": ol_score,
        "pbwr_pct": pbwr_pct,
        "sack_rate_pct": sack_rate_pct,
        "rb_ypc": rb_ypc,
        "rb_rush_ypg": round(rb_rush_ypg, 1),
    }


def fetch_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NFL170Game/2026"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_name(name: str) -> str:
    clean = name.lower().strip()
    for suffix in [" jr.", " jr", " sr.", " sr", " iii", " ii", " iv", " v", ".", "'", "-"]:
        clean = clean.replace(suffix, "")
    return " ".join(clean.split())


def rating_to_grade(ovr: int) -> str:
    if ovr >= 95:
        return "S"
    if ovr >= 91:
        return "A+"
    if ovr >= 87:
        return "A"
    if ovr >= 83:
        return "B+"
    if ovr >= 79:
        return "B"
    if ovr >= 75:
        return "C+"
    if ovr >= 71:
        return "C"
    if ovr >= 66:
        return "D"
    return "F"


def sync_all() -> Dict[str, Any]:
    print("1/5 Checking Sleeper NFL State & 2026/2027 Season Info...")
    nfl_state = {}
    try:
        nfl_state = fetch_json(SLEEPER_STATE_URL, timeout=15)
        print(f"  Sleeper NFL State: Season={nfl_state.get('season')}, Week={nfl_state.get('week')}, SeasonType={nfl_state.get('season_type')}")
    except Exception as e:
        print(f"  Warning fetching Sleeper state: {e}")

    print("2/5 Fetching Sleeper NFL players & 2026/2027 regular season stats...")
    sleeper_players = {}
    stats_2026 = {}
    stats_2025 = {}
    try:
        sleeper_players = fetch_json(SLEEPER_PLAYERS_URL, timeout=30)
        print(f"  Loaded {len(sleeper_players)} Sleeper player profiles.")
    except Exception as e:
        print(f"  Warning fetching Sleeper players: {e}")

    for yr, target in [("2026", stats_2026), ("2025", stats_2025)]:
        try:
            data = fetch_json(SLEEPER_STATS_URL.format(season=yr), timeout=25)
            if isinstance(data, dict):
                target.update(data)
                print(f"  Loaded {len(data)} stat entries for {yr} NFL season.")
        except Exception as e:
            print(f"  Note: stats for {yr} error: {e}")

    # Determine if 2026 stats have active games played
    active_2026_players = sum(1 for v in stats_2026.values() if isinstance(v, dict) and (v.get("gp", 0) or 0) > 0 and (v.get("pts_ppr", 0) or 0) > 5)
    print(f"  Active players with 2026 regular season fantasy points: {active_2026_players}")

    stats_by_espn_id: Dict[str, Dict[str, Any]] = {}
    stats_by_name_pos_team: Dict[str, Dict[str, Any]] = {}
    stats_by_name_pos: Dict[str, Dict[str, Any]] = {}

    for pid, pinfo in sleeper_players.items():
        if not isinstance(pinfo, dict):
            continue
        pos = pinfo.get("position")
        if pos not in ("QB", "RB", "WR", "TE", "DEF"):
            continue

        s26 = stats_2026.get(pid, {}) if isinstance(stats_2026.get(pid), dict) else {}
        s25 = stats_2025.get(pid, {}) if isinstance(stats_2025.get(pid), dict) else {}

        gp26 = float(s26.get("gp", 0) or 0)
        ppr26 = float(s26.get("pts_ppr", 0) or 0)
        gp25 = float(s25.get("gp", 0) or 0)
        ppr25 = float(s25.get("pts_ppr", 0) or 0)

        # Prioritize 2026 season stats!
        if active_2026_players >= 50 and gp26 > 0:
            chosen_stats = s26
            stat_season = "2026/27"
        elif ppr26 > 0:
            chosen_stats = s26
            stat_season = "2026/27"
        else:
            chosen_stats = s25
            stat_season = "2025/26"

        p_team = ABBR_MAP.get(pinfo.get("team") or "", pinfo.get("team") or "")
        full_name = pinfo.get("full_name") or f"{pinfo.get('first_name', '')} {pinfo.get('last_name', '')}".strip()

        entry = {
            "sleeper_id": pid,
            "espn_id": str(pinfo.get("espn_id") or ""),
            "full_name": full_name,
            "position": pos,
            "team": p_team,
            "depth_chart_order": pinfo.get("depth_chart_order"),
            "search_rank": pinfo.get("search_rank") or 9999,
            "age": pinfo.get("age"),
            "years_exp": pinfo.get("years_exp"),
            "college": pinfo.get("college"),
            "number": pinfo.get("number"),
            "stat_season": stat_season,
            "stats": chosen_stats,
            "stats_2026": s26,
            "stats_2025": s25,
        }
        if entry["espn_id"]:
            stats_by_espn_id[entry["espn_id"]] = entry

        norm = normalize_name(full_name)
        if p_team:
            stats_by_name_pos_team[f"{norm}|{pos}|{p_team}"] = entry

        key = f"{norm}|{pos}"
        existing = stats_by_name_pos.get(key)
        if not existing or (ppr26 > float(existing["stats_2026"].get("pts_ppr", 0) or 0)):
            stats_by_name_pos[key] = entry

    print("3/5 Fetching 2026/2027 ESPN Standings & 32 Teams...")
    standings_map: Dict[str, Dict[str, float]] = {}
    try:
        st_data = fetch_json(ESPN_STANDINGS_URL, timeout=20)
        for child in st_data.get("children", []) or []:
            for div in child.get("children", [child]) or []:
                entries = (div.get("standings") or {}).get("entries", []) or []
                for ent in entries:
                    t_obj = ent.get("team", {})
                    raw_ab = t_obj.get("abbreviation", "")
                    ab = ABBR_MAP.get(raw_ab, raw_ab)
                    st_dict = {s.get("name"): s.get("value", 0.0) for s in ent.get("stats", []) if isinstance(s, dict)}
                    standings_map[ab] = st_dict
        print(f"  Loaded live 2026/2027 standings for {len(standings_map)} teams.")
    except Exception as e:
        print(f"  Warning fetching standings: {e}")

    teams_resp = fetch_json(ESPN_TEAMS_URL)
    raw_teams = teams_resp.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])

    def fetch_team_bundle(t_wrapper: Dict[str, Any]) -> Dict[str, Any]:
        t = t_wrapper.get("team", {})
        tid = t.get("id")
        raw_abbr = t.get("abbreviation", "")
        abbr = ABBR_MAP.get(raw_abbr, raw_abbr)
        roster_data = {}
        depth_data = {}
        detail_data = {}
        try:
            roster_data = fetch_json(ESPN_ROSTER_URL.format(team_id=tid))
        except Exception as e:
            print(f"  Error fetching roster for {abbr}: {e}")
        try:
            depth_data = fetch_json(ESPN_DEPTH_URL.format(team_id=tid))
        except Exception:
            pass
        try:
            detail_data = fetch_json(ESPN_TEAM_DETAIL_URL.format(team_id=tid))
        except Exception:
            pass
        return {
            "id": tid,
            "abbr": abbr,
            "espn_abbr": raw_abbr,
            "name": t.get("displayName", ""),
            "short_name": t.get("shortDisplayName", ""),
            "location": t.get("location", ""),
            "nickname": t.get("name", ""),
            "color": f"#{t.get('color', '1a1a2e')}",
            "alt_color": f"#{t.get('alternateColor', 'ffffff')}",
            "logo": (t.get("logos") or [{}])[0].get("href", f"https://a.espncdn.com/i/teamlogos/nfl/500/{raw_abbr.lower()}.png"),
            "roster": roster_data,
            "depth": depth_data,
            "detail": detail_data,
        }

    print("4/5 Fetching 2026/2027 rosters & depth charts for all 32 teams in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        team_bundles = list(executor.map(fetch_team_bundle, raw_teams))

    print("5/5 Computing 2026/2027 Per-Position Rankings (#1..#N) & 0-99 OVR Ratings...")
    all_teams_out: Dict[str, Any] = {}
    all_skill_players: List[Dict[str, Any]] = []
    team_unit_metrics: Dict[str, Dict[str, Any]] = {}

    for tb in team_bundles:
        abbr = tb["abbr"]

        # Extract coach from roster data if present
        coach_list = tb.get("roster", {}).get("coach", []) or []
        hc_name = COACHES_2026.get(abbr, f"{tb['short_name']} Head Coach")
        if coach_list and isinstance(coach_list[0], dict):
            fn = coach_list[0].get("firstName", "")
            ln = coach_list[0].get("lastName", "")
            if fn or ln:
                hc_name = f"{fn} {ln}".strip()

        # Extract 2026 record & scoring stats from detail or standings
        st_info = standings_map.get(abbr, {})
        wins_26 = float(st_info.get("wins", 0) or 0)
        losses_26 = float(st_info.get("losses", 0) or 0)
        ties_26 = float(st_info.get("ties", 0) or 0)
        pf_26 = float(st_info.get("pointsFor", 0) or 0)
        pa_26 = float(st_info.get("pointsAgainst", 0) or 0)

        # Fallback to team detail record if standings_map was empty
        if (wins_26 + losses_26) == 0:
            rec_items = (tb.get("detail", {}).get("team", {}).get("record", {}) or {}).get("items", []) or []
            if rec_items:
                for st_s in rec_items[0].get("stats", []) or []:
                    if st_s.get("name") == "wins":
                        wins_26 = float(st_s.get("value", 0) or 0)
                    elif st_s.get("name") == "losses":
                        losses_26 = float(st_s.get("value", 0) or 0)
                    elif st_s.get("name") == "pointsFor":
                        pf_26 = float(st_s.get("value", 0) or 0)
                    elif st_s.get("name") == "pointsAgainst":
                        pa_26 = float(st_s.get("value", 0) or 0)

        gp_team = max(1.0, wins_26 + losses_26 + ties_26)
        win_pct = (wins_26 + 0.5 * ties_26) / gp_team
        ppg_for = pf_26 / gp_team if pf_26 > 0 else 22.0
        ppg_against = pa_26 / gp_team if pa_26 > 0 else 22.0

        team_unit_metrics[abbr] = {
            "hc_name": hc_name,
            "wins": int(wins_26),
            "losses": int(losses_26),
            "ties": int(ties_26),
            "gp": int(gp_team),
            "win_pct": win_pct,
            "ppg_for": round(ppg_for, 1),
            "ppg_against": round(ppg_against, 1),
        }

        # Parse depth chart order from ESPN depthcharts endpoint
        # Maps athlete_id -> (slot_priority, depth_rank)
        depth_order_map: Dict[str, int] = {}
        for dc in tb.get("depth", {}).get("items", []) or []:
            pos_map = dc.get("positions", {}) or {}
            for pos_key, pos_obj in pos_map.items():
                athletes = pos_obj.get("athletes", []) or []
                for idx, ath_entry in enumerate(athletes):
                    ath = ath_entry.get("athlete", ath_entry)
                    aid = str(ath.get("id", ""))
                    if aid:
                        rank_val = idx + 1
                        if aid not in depth_order_map or rank_val < depth_order_map[aid]:
                            depth_order_map[aid] = rank_val

        team_players: List[Dict[str, Any]] = []
        seen_ids = set()

        for group in tb.get("roster", {}).get("athletes", []) or []:
            for item in group.get("items", []) or []:
                pos_abbr = (item.get("position") or {}).get("abbreviation", "")
                if pos_abbr == "FB":
                    pos_abbr = "RB"
                if pos_abbr not in ("QB", "RB", "WR", "TE"):
                    continue

                espn_id = str(item.get("id", ""))
                if not espn_id or espn_id in seen_ids:
                    continue
                seen_ids.add(espn_id)

                # Skip players on Injured Reserve / Practice Squad if status indicates inactive, unless starter
                status_type = ((item.get("status") or {}).get("type") or "").lower()

                full_name = item.get("fullName") or item.get("displayName") or ""
                headshot = (item.get("headshot") or {}).get("href") or f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"
                jersey = item.get("jersey") or ""
                age = item.get("age")
                exp = (item.get("experience") or {}).get("years", 0)
                college = (item.get("college") or {}).get("name", "")

                # Match with Sleeper 2026 stats: first by ESPN ID, then by Name+Pos+Team, then Name+Pos
                sl_entry = stats_by_espn_id.get(espn_id)
                norm = normalize_name(full_name)
                if not sl_entry:
                    sl_entry = stats_by_name_pos_team.get(f"{norm}|{pos_abbr}|{abbr}")
                if not sl_entry:
                    sl_entry = stats_by_name_pos.get(f"{norm}|{pos_abbr}")

                s26 = (sl_entry or {}).get("stats_2026", {}) or {}
                s25 = (sl_entry or {}).get("stats_2025", {}) or {}

                ppr_26 = float(s26.get("pts_ppr", 0) or 0)
                gp_26 = int(s26.get("gp", 0) or 0)
                ppr_25 = float(s25.get("pts_ppr", 0) or 0)
                gp_25 = int(s25.get("gp", 0) or 0)

                # Use 2026 season stats primarily!
                if gp_26 > 0 or ppr_26 > 0:
                    active_st = s26
                    pts_ppr = ppr_26
                    gp = max(1, gp_26)
                    stat_season_label = "2026/27"
                elif gp_25 > 0 and ppr_25 > 0:
                    active_st = s25
                    pts_ppr = ppr_25 * 0.75  # Discounted if no 2026 stats yet
                    gp = max(1, gp_25)
                    stat_season_label = "2025/26"
                else:
                    active_st = {}
                    pts_ppr = 0.0
                    gp = 0
                    stat_season_label = "2026/27"

                ppg = pts_ppr / gp if gp > 0 else 0.0
                search_rank = int((sl_entry or {}).get("search_rank") or 9999)
                dc_order = depth_order_map.get(espn_id) or (sl_entry or {}).get("depth_chart_order") or 99

                player_obj = {
                    "id": f"{abbr}_{pos_abbr}_{espn_id}",
                    "espn_id": espn_id,
                    "name": full_name,
                    "team": abbr,
                    "team_name": tb["name"],
                    "position": pos_abbr,
                    "jersey": str(jersey),
                    "headshot": headshot,
                    "age": age,
                    "experience": exp,
                    "college": college,
                    "status": status_type,
                    "stat_season": stat_season_label,
                    "depth_order": int(dc_order),
                    "search_rank": search_rank,
                    "pts_ppr": round(pts_ppr, 1),
                    "ppg_ppr": round(ppg, 1),
                    "gp": gp,
                    "pass_att": int(active_st.get("pass_att", 0) or 0),
                    "pass_sack": int(active_st.get("pass_sack", 0) or 0),
                    "pass_yd": int(active_st.get("pass_yd", 0) or 0),
                    "pass_td": int(active_st.get("pass_td", 0) or 0),
                    "pass_int": int(active_st.get("pass_int", 0) or 0),
                    "rush_att": int(active_st.get("rush_att", 0) or 0),
                    "rush_yd": int(active_st.get("rush_yd", 0) or 0),
                    "rush_td": int(active_st.get("rush_td", 0) or 0),
                    "rec": int(active_st.get("rec", 0) or 0),
                    "rec_yd": int(active_st.get("rec_yd", 0) or 0),
                    "rec_td": int(active_st.get("rec_td", 0) or 0),
                }
                team_players.append(player_obj)
                all_skill_players.append(player_obj)

        all_teams_out[abbr] = {
            "id": tb["id"],
            "abbr": abbr,
            "name": tb["name"],
            "short_name": tb["short_name"],
            "location": tb["location"],
            "nickname": tb["nickname"],
            "color": tb["color"],
            "alt_color": tb["alt_color"],
            "logo": tb["logo"],
            "record_2026": f"{team_unit_metrics[abbr]['wins']}-{team_unit_metrics[abbr]['losses']}" + (f"-{team_unit_metrics[abbr]['ties']}" if team_unit_metrics[abbr]['ties'] else ""),
            "players": team_players,
        }

    # Compute 2026/2027 League-Wide Positional Rankings (#1, #2, #3... per position!)
    pos_counts: Dict[str, int] = {}
    for pos in ("QB", "RB", "WR", "TE"):
        pos_players = [p for p in all_skill_players if p["position"] == pos]
        for p in pos_players:
            p["_raw_score"] = compute_player_raw_score(p)

        pos_players.sort(key=lambda x: (x["_raw_score"], x["pts_ppr"], -x["depth_order"]), reverse=True)
        pos_counts[pos] = len(pos_players)

        for rank_idx, p in enumerate(pos_players):
            pos_rank = rank_idx + 1
            p["pos_rank"] = pos_rank
            p["pos_total"] = 32 if pos in ("QB", "TE") else 64

            if pos in ("QB", "TE"):
                if pos_rank == 1:
                    ovr = 99
                elif pos_rank == 2:
                    ovr = 97
                elif pos_rank == 3:
                    ovr = 96
                elif pos_rank <= 6:
                    ovr = 95 - (pos_rank - 4)
                elif pos_rank <= 10:
                    ovr = 91 - (pos_rank - 7)
                elif pos_rank <= 16:
                    ovr = 87 - int((pos_rank - 11) * 0.8)
                elif pos_rank <= 24:
                    ovr = 82 - int((pos_rank - 17) * 0.75)
                elif pos_rank <= 32:
                    ovr = 76 - int((pos_rank - 25) * 0.75)
                elif pos_rank <= 48:
                    ovr = 70 - int((pos_rank - 33) * 0.4)
                else:
                    ovr = max(58, 63 - int((pos_rank - 49) * 0.2))
            else:
                if pos_rank == 1:
                    ovr = 99
                elif pos_rank == 2:
                    ovr = 98
                elif pos_rank <= 5:
                    ovr = 97 - (pos_rank - 3)
                elif pos_rank <= 10:
                    ovr = 94 - int((pos_rank - 6) * 0.8)
                elif pos_rank <= 20:
                    ovr = 90 - int((pos_rank - 11) * 0.5)
                elif pos_rank <= 32:
                    ovr = 85 - int((pos_rank - 21) * 0.45)
                elif pos_rank <= 48:
                    ovr = 79 - int((pos_rank - 33) * 0.35)
                elif pos_rank <= 64:
                    ovr = 73 - int((pos_rank - 49) * 0.3)
                else:
                    ovr = max(58, 68 - int((pos_rank - 65) * 0.15))

            p["ovr"] = int(max(55, min(99, ovr)))
            p["grade"] = rating_to_grade(p["ovr"])

            if pos == "QB":
                tot_yds = p["pass_yd"] + p["rush_yd"]
                p["stat_line"] = (
                    f"{p['pass_yd']:,} PASS YDS • {p['pass_td']} TD • {p['rush_yd']} RUSH YDS • {p['pts_ppr']} FPTS (2026/27)"
                    if tot_yds > 0
                    else "NFL Roster QB (2026/27)"
                )
            elif pos == "RB":
                p["stat_line"] = (
                    f"{p['rush_yd']:,} RUSH YDS • {p['rush_td']} TD • {p['rec']} REC ({p['rec_yd']} YDS) • {p['pts_ppr']} FPTS (2026/27)"
                    if (p["rush_yd"] + p["rec_yd"]) > 0
                    else "NFL Roster RB (2026/27)"
                )
            else:
                p["stat_line"] = (
                    f"{p['rec']} REC • {p['rec_yd']:,} REC YDS • {p['rec_td']} TD • {p['pts_ppr']} FPTS (2026/27)"
                    if p["rec_yd"] > 0
                    else f"NFL Roster {pos} (2026/27)"
                )
            p.pop("_raw_score", None)

    # Compute 2026/2027 OL, DEF, and HC rankings (#1 to #32)
    # OL Rank: strictly from Trench / Pass-Block + Run-Block metrics (no Offense PPG!)
    for abbr, m in team_unit_metrics.items():
        t_players = all_teams_out[abbr]["players"]
        ol_metrics = compute_ol_trench_metrics(abbr, t_players, m["gp"])
        m.update(ol_metrics)
        # DEF Rank: lower PPG allowed is better + win_pct
        m["def_score"] = (40.0 - m["ppg_against"]) * 3.0 + m["win_pct"] * 12.0
        # HC Rank: 2026 Win % + Points Differential
        m["hc_score"] = m["win_pct"] * 60.0 + (m["ppg_for"] - m["ppg_against"]) * 1.5

    ol_sorted = sorted(team_unit_metrics.items(), key=lambda x: x[1]["ol_score"], reverse=True)
    def_sorted = sorted(team_unit_metrics.items(), key=lambda x: x[1]["def_score"], reverse=True)
    hc_sorted = sorted(team_unit_metrics.items(), key=lambda x: x[1]["hc_score"], reverse=True)

    def rank_to_unit_ovr(rank_1_to_32: int) -> int:
        # Maps #1 -> 98 OVR down to #32 -> 68 OVR
        return int(round(98 - (rank_1_to_32 - 1) * (30.0 / 31.0)))

    ol_rank_map = {k: i + 1 for i, (k, _) in enumerate(ol_sorted)}
    def_rank_map = {k: i + 1 for i, (k, _) in enumerate(def_sorted)}
    hc_rank_map = {k: i + 1 for i, (k, _) in enumerate(hc_sorted)}

    for abbr, tdata in all_teams_out.items():
        players = tdata["players"]
        kept_players: List[Dict[str, Any]] = []
        limits = {"QB": 2, "RB": 3, "WR": 4, "TE": 2}
        for pos in ("QB", "RB", "WR", "TE"):
            pos_list = [p for p in players if p["position"] == pos]
            pos_list.sort(key=lambda x: (x["ovr"], x["pts_ppr"], -x["depth_order"]), reverse=True)
            top_n = pos_list[:limits[pos]]
            for idx, p in enumerate(top_n):
                p["depth_label"] = f"{pos}{idx + 1}"
                p["is_starter"] = (idx == 0) or (pos == "WR" and idx <= 2) or (pos == "RB" and idx <= 1)
                kept_players.append(p)

        m = team_unit_metrics[abbr]
        ol_rk = ol_rank_map[abbr]
        def_rk = def_rank_map[abbr]
        hc_rk = hc_rank_map[abbr]

        ol_ovr = rank_to_unit_ovr(ol_rk)
        def_ovr = rank_to_unit_ovr(def_rk)
        hc_ovr = rank_to_unit_ovr(hc_rk)

        ol_unit = {
            "id": f"{abbr}_OL",
            "espn_id": "",
            "name": f"{tdata['name']} OL",
            "team": abbr,
            "team_name": tdata["name"],
            "position": "OL",
            "jersey": "OL",
            "headshot": tdata["logo"],
            "age": None,
            "experience": None,
            "college": "",
            "stat_season": "2026/27",
            "depth_order": 1,
            "depth_label": "OL1",
            "is_starter": True,
            "pts_ppr": 0.0,
            "ppg_ppr": 0.0,
            "gp": m["gp"],
            "pos_rank": ol_rk,
            "pos_total": 32,
            "ovr": ol_ovr,
            "grade": rating_to_grade(ol_ovr),
            "stat_line": (
                f"#{ol_rk} NFL OL • {m['pbwr_pct']}% Pass Block Win • "
                f"{m['rb_ypc']:.1f} RB YPC ({m['rb_rush_ypg']:.0f} Rush YPG) • "
                f"{m['sack_rate_pct']:.1f}% Sack Rate"
            ),
        }
        def_unit = {
            "id": f"{abbr}_DEF",
            "espn_id": "",
            "name": f"{tdata['name']} Defense",
            "team": abbr,
            "team_name": tdata["name"],
            "position": "DEF",
            "jersey": "DEF",
            "headshot": tdata["logo"],
            "age": None,
            "experience": None,
            "college": "",
            "stat_season": "2026/27",
            "depth_order": 1,
            "depth_label": "DEF1",
            "is_starter": True,
            "pts_ppr": 0.0,
            "ppg_ppr": 0.0,
            "gp": m["gp"],
            "pos_rank": def_rk,
            "pos_total": 32,
            "ovr": def_ovr,
            "grade": rating_to_grade(def_ovr),
            "stat_line": f"#{def_rk} NFL Defense (2026/27) • {m['ppg_against']} PPG Allowed ({tdata['record_2026']})",
        }
        hc_unit = {
            "id": f"{abbr}_HC",
            "espn_id": "",
            "name": m["hc_name"],
            "team": abbr,
            "team_name": tdata["name"],
            "position": "HC",
            "jersey": "HC",
            "headshot": tdata["logo"],
            "age": None,
            "experience": None,
            "college": "",
            "stat_season": "2026/27",
            "depth_order": 1,
            "depth_label": "HC",
            "is_starter": True,
            "pts_ppr": 0.0,
            "ppg_ppr": 0.0,
            "gp": m["gp"],
            "pos_rank": hc_rk,
            "pos_total": 32,
            "ovr": hc_ovr,
            "grade": rating_to_grade(hc_ovr),
            "stat_line": f"#{hc_rk} NFL Head Coach (2026/27) • Bilanz {tdata['record_2026']}",
        }

        kept_players.extend([ol_unit, def_unit, hc_unit])
        tdata["players"] = kept_players

    # Also build a clean top-rankings leaderboard per position (#1..#32) for the frontend!
    leaderboards: Dict[str, List[Dict[str, Any]]] = {}
    for pos in ("QB", "RB", "WR", "TE", "OL", "DEF", "HC"):
        all_pos = [
            p for t in all_teams_out.values() for p in t["players"]
            if p["position"] == pos
        ]
        all_pos.sort(key=lambda x: x["pos_rank"])
        # Re-normalize sequential rank 1..N among the kept active NFL roster players
        for idx, p in enumerate(all_pos):
            p["pos_rank"] = idx + 1
            p["pos_total"] = len(all_pos)
        leaderboards[pos] = [
            {
                "id": p["id"],
                "name": p["name"],
                "team": p["team"],
                "position": p["position"],
                "pos_rank": p["pos_rank"],
                "pos_total": p["pos_total"],
                "ovr": p["ovr"],
                "grade": p["grade"],
                "pts_ppr": p["pts_ppr"],
                "stat_line": p["stat_line"],
                "headshot": p["headshot"],
            }
            for p in all_pos[:32]
        ]

    output = {
        "source": "ESPN NFL API + Sleeper API (Saison 2026/2027 Live)",
        "season": "2026/2027",
        "nfl_state": nfl_state,
        "team_count": len(all_teams_out),
        "teams": all_teams_out,
        "leaderboards": leaderboards,
    }
    saved_path = write_cache_json(output)
    print(f"Successfully synced 2026/2027 NFL data ({len(all_teams_out)} teams) to {saved_path}")
    return output


if __name__ == "__main__":
    sync_all()
