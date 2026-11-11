"""
Game Engine for NFL Build A 17-0 Team (Saison 2026/2027).
Exclusive Ultimate 10-Slot Mode (QB, 2x RB, 2x WR, 2x TE, OL, DEF, HC),
HMAC session signing & anti-cheat validation, thread-safe data store with
daily background sync support, 17-game season simulation, Per-Position Rankings (#1..#N),
and exact Bitmask-DP Optimal Lineup calculation.
"""
import hashlib
import hmac
import json
import os
import random
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from calibrate_data import calibrate_cached_data
from sync_live_nfl import get_readable_cache_file, rating_to_grade, sync_all

ULTIMATE_SLOTS: List[Dict[str, Any]] = [
    {"slot_id": "QB", "label": "QB", "allowed": ["QB"], "weight": 1.45, "color": "#7c2d36"},
    {"slot_id": "RB1", "label": "RB", "allowed": ["RB"], "weight": 0.95, "color": "#14532d"},
    {"slot_id": "RB2", "label": "RB", "allowed": ["RB"], "weight": 0.85, "color": "#14532d"},
    {"slot_id": "WR1", "label": "WR", "allowed": ["WR"], "weight": 1.00, "color": "#1e3a8a"},
    {"slot_id": "WR2", "label": "WR", "allowed": ["WR"], "weight": 0.95, "color": "#1e3a8a"},
    {"slot_id": "TE1", "label": "TE", "allowed": ["TE"], "weight": 0.90, "color": "#78350f"},
    {"slot_id": "TE2", "label": "TE", "allowed": ["TE"], "weight": 0.80, "color": "#78350f"},
    {"slot_id": "OL", "label": "OL", "allowed": ["OL"], "weight": 1.15, "color": "#115e59"},
    {"slot_id": "DEF", "label": "DEF", "allowed": ["DEF"], "weight": 1.20, "color": "#3b0764"},
    {"slot_id": "HC", "label": "HC", "allowed": ["HC"], "weight": 1.05, "color": "#713f12"},
]

ROSTER_MODES: Dict[str, List[Dict[str, Any]]] = {
    "ultimate": ULTIMATE_SLOTS,
}

_SESSION_SECRET = os.environ.get(
    "NFL170_SESSION_SECRET",
    "nfl-17-0-ultimate-hmac-secret-2026-v1",
).encode("utf-8")


def sign_drawn_teams(drawn_teams: List[str]) -> str:
    payload = ",".join(drawn_teams).encode("utf-8")
    return hmac.new(_SESSION_SECRET, payload, hashlib.sha256).hexdigest()


def verify_drawn_teams(drawn_teams: List[str], token: Optional[str]) -> bool:
    if not token or not drawn_teams:
        return False
    expected = sign_drawn_teams(drawn_teams)
    return hmac.compare_digest(expected, str(token))


class NFLDataStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.data: Dict[str, Any] = {}
        self.last_sync_epoch: float = 0.0
        self.load_or_sync()

    def load_or_sync(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            cache_path = get_readable_cache_file()
            if not force and cache_path.exists():
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if loaded.get("team_count", 0) >= 30:
                        self.data = loaded
                        self.last_sync_epoch = cache_path.stat().st_mtime
                        return self.data
                except Exception as e:
                    print(f"Error reading cache file: {e}")

            sync_all()
            calibrate_cached_data()
            cache_path = get_readable_cache_file()
            with open(cache_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            self.last_sync_epoch = time.time()
            return self.data

    def sync_if_stale(self, max_age_hours: float = 24.0) -> bool:
        """Runs a live data sync & calibration if cache is older than max_age_hours."""
        try:
            cache_path = get_readable_cache_file()
            if cache_path.exists():
                age_hours = (time.time() - cache_path.stat().st_mtime) / 3600.0
                if age_hours < max_age_hours:
                    return False
            self.load_or_sync(force=True)
            return True
        except Exception as e:
            print(f"[DailySync] Warning: background sync failed, keeping cached data: {e}")
            return False

    def get_teams(self) -> Dict[str, Any]:
        with self._lock:
            return self.data.get("teams", {})

    def get_leaderboards(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._lock:
            return self.data.get("leaderboards", {})

    def mask_player_for_draft(self, p: Dict[str, Any], team_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Return player data without spoiling OVR, grade, or rank during the draft."""
        return {
            "id": p["id"],
            "espn_id": p.get("espn_id", ""),
            "name": p["name"],
            "team": p["team"],
            "team_name": p["team_name"],
            "team_color": team_obj.get("color", "#1a1a2e"),
            "team_alt_color": team_obj.get("alt_color", "#ffffff"),
            "position": p["position"],
            "jersey": p.get("jersey", ""),
            "headshot": p.get("headshot", ""),
            "age": p.get("age"),
            "experience": p.get("experience"),
            "college": p.get("college", ""),
            "depth_order": p.get("depth_order", 1),
            "depth_label": p.get("depth_label", p["position"]),
            "is_starter": p.get("is_starter", True),
        }


store = NFLDataStore()


def generate_game_teams(seed_str: Optional[str] = None) -> Dict[str, Any]:
    slots = ULTIMATE_SLOTS
    num_rounds = len(slots)
    teams_dict = store.get_teams()
    all_abbrs = sorted(teams_dict.keys())

    if seed_str:
        seed_int = int(hashlib.sha256(str(seed_str).encode("utf-8")).hexdigest()[:12], 16)
        rng = random.Random(seed_int)
    else:
        rng = random.Random()

    chosen_abbrs = rng.sample(all_abbrs, k=min(num_rounds, len(all_abbrs)))
    session_token = sign_drawn_teams(chosen_abbrs)

    rounds_payload = []
    for idx, abbr in enumerate(chosen_abbrs):
        t = teams_dict[abbr]
        rounds_payload.append({
            "round": idx + 1,
            "abbr": t["abbr"],
            "name": t["name"],
            "short_name": t["short_name"],
            "location": t["location"],
            "nickname": t["nickname"],
            "color": t["color"],
            "alt_color": t["alt_color"],
            "logo": t.get("logo", ""),
            "record_2026": t.get("record_2026", ""),
            "players": [store.mask_player_for_draft(p, t) for p in t["players"]],
        })

    return {
        "mode": "ultimate",
        "season": store.data.get("season", "2026/2027"),
        "session_token": session_token,
        "total_rounds": num_rounds,
        "slots": slots,
        "rounds": rounds_payload,
    }


def calculate_wins_and_schedule(
    weighted_ovr: float,
    off_ovr: float,
    def_ovr: float,
    picks_detail: List[Dict[str, Any]],
    drawn_teams: List[str],
) -> Dict[str, Any]:
    teams_dict = store.get_teams()

    qb_pick = next((p for p in picks_detail if p["slot_id"] == "QB"), None)
    qb_ovr = qb_pick["player"]["ovr"] if qb_pick else 75
    min_ovr = min((p["player"]["ovr"] for p in picks_detail), default=75)

    effective_ovr = weighted_ovr
    bottleneck_note = None
    if qb_ovr < 74 and qb_pick:
        penalty = (74 - qb_ovr) * 0.22
        effective_ovr -= penalty
        bottleneck_note = (
            f"QB-Bottleneck ({qb_pick['player']['name']}, "
            f"#{qb_pick['player']['pos_rank']} QB, {qb_ovr} OVR) hat die Offensive limitiert."
        )
    elif min_ovr < 68 and picks_detail:
        weakest = min(picks_detail, key=lambda x: x["player"]["ovr"])
        penalty = (68 - min_ovr) * 0.15
        effective_ovr -= penalty
        bottleneck_note = (
            f"Schwachstelle auf {weakest['slot_label']} ({weakest['player']['name']}, "
            f"#{weakest['player']['pos_rank']} {weakest['player']['position']}, {min_ovr} OVR) hat knappe Spiele gekostet."
        )

    thresholds = [
        (89.5, 17),
        (88.2, 16),
        (86.8, 15),
        (85.4, 14),
        (84.0, 13),
        (82.5, 12),
        (81.0, 11),
        (79.5, 10),
        (78.0, 9),
        (76.4, 8),
        (74.8, 7),
        (73.2, 6),
        (71.5, 5),
        (69.8, 4),
        (67.8, 3),
        (65.5, 2),
        (63.0, 1),
    ]
    target_wins = 0
    for thresh, w in thresholds:
        if effective_ovr >= thresh:
            target_wins = w
            break

    all_opp_abbrs = [a for a in sorted(teams_dict.keys())]
    seed_str = "-".join(f"{p['slot_id']}:{p['player']['id']}" for p in picks_detail)
    rng = random.Random(int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:10], 16))
    schedule_opps = rng.sample(all_opp_abbrs, k=17)

    opp_list = []
    for week_idx, opp_abbr in enumerate(schedule_opps):
        opp_team = teams_dict[opp_abbr]
        opp_players = opp_team["players"]
        opp_avg = sum(p["ovr"] for p in opp_players[:8]) / max(1, len(opp_players[:8]))
        is_home = (week_idx % 2 == 0)
        difficulty = opp_avg + (0.0 if is_home else 1.8) + rng.uniform(-1.5, 1.5)
        opp_list.append({
            "week": week_idx + 1,
            "opponent_abbr": opp_abbr,
            "opponent_name": opp_team["name"],
            "opponent_color": opp_team.get("color", "#1a1a2e"),
            "opponent_alt_color": opp_team.get("alt_color", "#ffffff"),
            "opponent_logo": opp_team.get("logo", ""),
            "is_home": is_home,
            "difficulty": round(difficulty, 1),
        })

    by_diff = sorted(opp_list, key=lambda x: x["difficulty"])
    won_weeks = {g["week"] for g in by_diff[:target_wins]}

    schedule_results = []
    for g in opp_list:
        won = g["week"] in won_weeks
        base_pts = int(round((off_ovr - 65) * 0.65 + 14))
        opp_pts_base = int(round(32 - (def_ovr - 65) * 0.55))
        if won:
            my_score = max(17, base_pts + rng.randint(2, 12))
            their_score = max(7, min(my_score - rng.choice([3, 4, 6, 7, 10, 14]), opp_pts_base))
        else:
            their_score = max(20, opp_pts_base + rng.randint(3, 10))
            my_score = max(10, min(their_score - rng.choice([1, 3, 3, 6, 7]), base_pts))
        if my_score == their_score:
            if won:
                my_score += 3
            else:
                their_score += 3

        schedule_results.append({
            **g,
            "result": "W" if won else "L",
            "score": f"{my_score}-{their_score}",
            "my_score": my_score,
            "opp_score": their_score,
        })

    losses = 17 - target_wins
    if target_wins == 17:
        tier_title = "PERFECT 17-0 DYNASTY 🏆"
        playoff_finish = "Undefeated Champions (17-0)"
        summary_de = "Perfektion! Dein 2026/27 Roster dominiert jede Phase des Spiels ohne eine einzige Schwachstelle."
    elif target_wins >= 15:
        tier_title = "CHAMPIONSHIP DYNASTY 🏆"
        playoff_finish = "#1 Seed & Title Winner"
        summary_de = f"Fast perfekt ({target_wins}-{losses})! Nur Nuancen haben zum legendären 17-0 gefehlt."
    elif target_wins >= 13:
        tier_title = "TITLE CONTENDER"
        playoff_finish = "Conference Finalist / Division Winner"
        summary_de = f"Elitäres Playoff-Team ({target_wins}-{losses}), aber 1–2 Positionen haben das 17-0 verhindert."
    elif target_wins >= 10:
        tier_title = "PLAYOFF WILD CARD"
        playoff_finish = "Wild Card / Divisional Round"
        summary_de = f"Solides Playoff-Roster ({target_wins}-{losses}) mit klaren Stärken, aber einigen Lücken."
    elif target_wins >= 7:
        tier_title = "IN THE HUNT (MEDIOCRE)"
        playoff_finish = "Missed Playoffs"
        summary_de = f"Durchschnittliches Team ({target_wins}-{losses}). Zu viele Backup- oder C-Tier-Picks."
    else:
        tier_title = "TOP DRAFT PICK REBUILD"
        playoff_finish = "#1 Overall Draft Pick Contender"
        summary_de = f"Harte Saison ({target_wins}-{losses}). Hier müssen dringend mehr Top-5 Starter her!"

    return {
        "wins": target_wins,
        "losses": losses,
        "record": f"{target_wins}-{losses}",
        "is_perfect": target_wins == 17,
        "effective_ovr": round(effective_ovr, 1),
        "tier_title": tier_title,
        "playoff_finish": playoff_finish,
        "summary_de": summary_de,
        "bottleneck_note": bottleneck_note,
        "schedule": schedule_results,
    }


def solve_optimal_lineup(drawn_team_abbrs: List[str]) -> Dict[str, Any]:
    slots = ULTIMATE_SLOTS
    n_slots = len(slots)
    teams_dict = store.get_teams()

    rounds_teams = [teams_dict[abbr] for abbr in drawn_team_abbrs[:n_slots] if abbr in teams_dict]
    if len(rounds_teams) != n_slots:
        return {}

    total_weight = sum(s["weight"] for s in slots)

    best_choice: List[List[Optional[Dict[str, Any]]]] = [[None] * n_slots for _ in range(n_slots)]
    for r_idx, tdata in enumerate(rounds_teams):
        for s_idx, slot in enumerate(slots):
            allowed = slot["allowed"]
            candidates = [p for p in tdata["players"] if p["position"] in allowed]
            if candidates:
                best_p = max(candidates, key=lambda x: x["ovr"])
                best_choice[r_idx][s_idx] = {
                    **best_p,
                    "team_color": tdata.get("color", "#1a1a2e"),
                    "team_alt_color": tdata.get("alt_color", "#ffffff"),
                }

    dp: Dict[int, Tuple[float, List[Tuple[int, int, Dict[str, Any]]]]] = {0: (0.0, [])}

    for r_idx in range(n_slots):
        next_dp: Dict[int, Tuple[float, List[Tuple[int, int, Dict[str, Any]]]]] = {}
        for mask, (cur_score, cur_path) in dp.items():
            for s_idx in range(n_slots):
                if not (mask & (1 << s_idx)):
                    cand = best_choice[r_idx][s_idx]
                    if cand is None:
                        continue
                    w = slots[s_idx]["weight"]
                    bonus = 0.0
                    if slots[s_idx]["slot_id"] == "QB" and cand["ovr"] < 74:
                        bonus = -8.0
                    new_score = cur_score + cand["ovr"] * w + bonus
                    new_mask = mask | (1 << s_idx)
                    if new_mask not in next_dp or new_score > next_dp[new_mask][0]:
                        next_dp[new_mask] = (new_score, cur_path + [(r_idx, s_idx, cand)])
        dp = next_dp

    full_mask = (1 << n_slots) - 1
    if full_mask not in dp:
        return {}

    _, optimal_path = dp[full_mask]
    opt_weighted_sum = sum(p["ovr"] * slots[s_idx]["weight"] for _, s_idx, p in optimal_path)
    opt_ovr = opt_weighted_sum / total_weight

    opt_picks_detail = []
    for r_idx, s_idx, p in optimal_path:
        slot = slots[s_idx]
        opt_picks_detail.append({
            "round": r_idx + 1,
            "team_abbr": drawn_team_abbrs[r_idx],
            "slot_id": slot["slot_id"],
            "slot_label": slot["label"],
            "player": p,
        })

    opt_off = [x["player"]["ovr"] for x in opt_picks_detail if x["slot_id"] not in ("DEF", "HC")]
    opt_def = [x["player"]["ovr"] for x in opt_picks_detail if x["slot_id"] in ("DEF", "HC")]
    opt_sim = calculate_wins_and_schedule(
        weighted_ovr=opt_ovr,
        off_ovr=sum(opt_off) / max(1, len(opt_off)),
        def_ovr=sum(opt_def) / max(1, len(opt_def)),
        picks_detail=opt_picks_detail,
        drawn_teams=drawn_team_abbrs,
    )

    return {
        "optimal_ovr": round(opt_ovr, 1),
        "optimal_grade": rating_to_grade(int(round(opt_ovr))),
        "optimal_record": opt_sim["record"],
        "optimal_wins": opt_sim["wins"],
        "optimal_losses": opt_sim["losses"],
        "picks_by_round": sorted(opt_picks_detail, key=lambda x: x["round"]),
    }


def evaluate_roster(
    drawn_teams: List[str],
    user_picks: List[Dict[str, Any]],
    session_token: Optional[str] = None,
) -> Dict[str, Any]:
    slots = ULTIMATE_SLOTS
    slot_map = {s["slot_id"]: s for s in slots}
    teams_dict = store.get_teams()
    leaderboards = store.get_leaderboards()

    if not isinstance(drawn_teams, list) or len(drawn_teams) != len(slots):
        raise ValueError(f"Expected exactly {len(slots)} drawn teams for Ultimate mode.")

    # Verify HMAC session token if present (protects against forged team lists)
    if session_token is not None and not verify_drawn_teams(drawn_teams, session_token):
        raise ValueError("Invalid session signature for drawn teams.")

    player_lookup: Dict[str, Dict[str, Any]] = {}
    for t in teams_dict.values():
        for p in t["players"]:
            player_lookup[p["id"]] = {
                **p,
                "team_color": t.get("color", "#1a1a2e"),
                "team_alt_color": t.get("alt_color", "#ffffff"),
                "headshot": p.get("headshot", "") or t.get("logo", ""),
            }

    picks_detail: List[Dict[str, Any]] = []
    weighted_sum = 0.0
    total_weight = 0.0
    used_slots = set()
    used_rounds = set()

    for pick in user_picks:
        slot_id = str(pick.get("slot_id", ""))
        pid = str(pick.get("player_id", ""))
        round_num = int(pick.get("round", 0) or 0)

        slot_info = slot_map.get(slot_id)
        player = player_lookup.get(pid)
        if not slot_info or not player:
            raise ValueError(f"Invalid slot ({slot_id}) or player ({pid}).")
        if slot_id in used_slots:
            raise ValueError(f"Duplicate slot pick: {slot_id}")
        if round_num < 1 or round_num > len(slots) or round_num in used_rounds:
            raise ValueError(f"Invalid or duplicate round number: {round_num}")

        expected_team = drawn_teams[round_num - 1]
        if player["team"] != expected_team:
            raise ValueError(
                f"Anti-Cheat: Player {player['name']} ({player['team']}) does not belong to Round {round_num} team ({expected_team})."
            )
        if player["position"] not in slot_info["allowed"]:
            raise ValueError(
                f"Position mismatch: {player['position']} is not allowed in slot {slot_id}."
            )

        used_slots.add(slot_id)
        used_rounds.add(round_num)

        w = slot_info["weight"]
        weighted_sum += player["ovr"] * w
        total_weight += w

        team_obj = teams_dict.get(player["team"], {})
        same_slot_candidates = [
            cand for cand in team_obj.get("players", [])
            if cand["position"] in slot_info["allowed"]
        ]
        best_in_slot = max(same_slot_candidates, key=lambda x: x["ovr"]) if same_slot_candidates else player

        pos_lb = leaderboards.get(player["position"], [])
        num1_in_nfl = pos_lb[0] if pos_lb else None

        picks_detail.append({
            "round": round_num,
            "slot_id": slot_id,
            "slot_label": slot_info["label"],
            "weight": w,
            "player": player,
            "rank_badge": f"#{player['pos_rank']} {player['position']}",
            "best_on_team_for_slot": {
                "name": best_in_slot["name"],
                "ovr": best_in_slot["ovr"],
                "pos_rank": best_in_slot["pos_rank"],
                "position": best_in_slot["position"],
                "grade": best_in_slot["grade"],
                "was_optimal_on_team": best_in_slot["id"] == player["id"],
            },
            "nfl_number_one": {
                "name": num1_in_nfl["name"],
                "team": num1_in_nfl["team"],
                "ovr": num1_in_nfl["ovr"],
            } if num1_in_nfl else None,
        })

    if len(picks_detail) != len(slots):
        raise ValueError(f"Expected {len(slots)} valid picks, got {len(picks_detail)}.")

    team_ovr = (weighted_sum / total_weight) if total_weight > 0 else 70.0
    off_ovrs = [p["player"]["ovr"] for p in picks_detail if p["slot_id"] not in ("DEF", "HC")]
    def_ovrs = [p["player"]["ovr"] for p in picks_detail if p["slot_id"] in ("DEF", "HC")]
    off_ovr = sum(off_ovrs) / max(1, len(off_ovrs))
    def_ovr = sum(def_ovrs) / max(1, len(def_ovrs))

    sim = calculate_wins_and_schedule(
        weighted_ovr=team_ovr,
        off_ovr=off_ovr,
        def_ovr=def_ovr,
        picks_detail=picks_detail,
        drawn_teams=drawn_teams,
    )

    optimal = solve_optimal_lineup(drawn_teams)

    sorted_by_ovr = sorted(picks_detail, key=lambda x: (x["player"]["ovr"], -x["player"]["pos_rank"]), reverse=True)
    mvp = sorted_by_ovr[0] if sorted_by_ovr else None
    weakest = sorted_by_ovr[-1] if sorted_by_ovr else None

    # Enrich leaderboards with team colors so frontend can render team badges
    enriched_leaderboards: Dict[str, List[Dict[str, Any]]] = {}
    for pos, entries in leaderboards.items():
        enriched_leaderboards[pos] = [
            {
                **e,
                "headshot": e.get("headshot", "") or teams_dict.get(e["team"], {}).get("logo", ""),
                "team_color": teams_dict.get(e["team"], {}).get("color", "#1a1a2e"),
                "team_alt_color": teams_dict.get(e["team"], {}).get("alt_color", "#ffffff"),
            }
            for e in entries
        ]

    return {
        "mode": "ultimate",
        "season": store.data.get("season", "2026/2027"),
        "team_ovr": round(team_ovr, 1),
        "team_grade": rating_to_grade(int(round(team_ovr))),
        "offense_ovr": round(off_ovr, 1),
        "defense_ovr": round(def_ovr, 1),
        "wins": sim["wins"],
        "losses": sim["losses"],
        "record": sim["record"],
        "is_perfect": sim["is_perfect"],
        "tier_title": sim["tier_title"],
        "playoff_finish": sim["playoff_finish"],
        "summary_de": sim["summary_de"],
        "bottleneck_note": sim["bottleneck_note"],
        "mvp": mvp,
        "weakest_link": weakest,
        "picks": picks_detail,
        "schedule": sim["schedule"],
        "optimal_analysis": optimal,
        "leaderboards": enriched_leaderboards,
    }
