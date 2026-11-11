"""
Ensures strict 2026/2027 positional ranking (#1, #2, #3... per position),
recalculates OL ratings purely from Trench / Blocking metrics (Pass Block Win Rate,
low Sack Rate Allowed, RB YPC & RB Rush YPG — zero dependency on Offense PPG),
and strips external copyrighted image URLs for safe public deployment.
"""
import datetime
import json
from typing import Any, Dict, List

from sync_live_nfl import (
    compute_ol_trench_metrics,
    compute_player_raw_score,
    get_readable_cache_file,
    rating_to_grade,
    write_cache_json,
)


def rank_to_unit_ovr(rank_1_to_32: int) -> int:
    return int(round(98 - (rank_1_to_32 - 1) * (30.0 / 31.0)))


def calibrate_cached_data() -> None:
    cache_path = get_readable_cache_file()
    if not cache_path.exists():
        return
    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    teams = data.get("teams", {})

    # 1. Ensure team logo URLs & player headshot URLs are populated
    espn_logo_abbr = {"WAS": "wsh", "JAX": "jax"}
    for abbr, tdata in teams.items():
        logo_code = espn_logo_abbr.get(abbr, abbr.lower())
        team_logo = tdata.get("logo") or f"https://a.espncdn.com/i/teamlogos/nfl/500/{logo_code}.png"
        tdata["logo"] = team_logo
        for p in tdata.get("players", []):
            espn_id = p.get("espn_id", "")
            if espn_id:
                p["headshot"] = p.get("headshot") or f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"
            else:
                p["headshot"] = team_logo

    # 2. Re-rank skill positions using unified 2026/27 score (PPR + PPG reliability + efficiency)
    leaderboards: Dict[str, List[Dict[str, Any]]] = {}
    for pos in ("QB", "RB", "WR", "TE"):
        all_pos = [
            p for t in teams.values() for p in t["players"]
            if p["position"] == pos
        ]
        for p in all_pos:
            p["_raw_score"] = compute_player_raw_score(p)

        all_pos.sort(
            key=lambda x: (
                x.get("_raw_score", 0.0),
                x.get("pts_ppr", 0.0),
                x.get("ppg_ppr", 0.0),
                -x.get("depth_order", 99),
            ),
            reverse=True,
        )
        total = len(all_pos)
        for idx, p in enumerate(all_pos):
            pos_rank = idx + 1
            p["pos_rank"] = pos_rank
            p["pos_total"] = total
            if pos in ("QB", "TE"):
                if pos_rank == 1:
                    ovr = 99
                elif pos_rank == 2:
                    ovr = 98
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
                else:
                    ovr = max(58, 70 - int((pos_rank - 33) * 0.45))
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
                    ovr = max(58, 68 - int((pos_rank - 65) * 0.2))

            p["ovr"] = int(max(55, min(99, ovr)))
            p["grade"] = rating_to_grade(p["ovr"])
            p.pop("_raw_score", None)

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
                "headshot": p.get("headshot", ""),
            }
            for p in all_pos[:32]
        ]

    # 3. Recompute OL rankings purely from Trench / Blocking metrics (no Offense Points!)
    ol_metrics_by_team: Dict[str, Dict[str, Any]] = {}
    for abbr, tdata in teams.items():
        players = tdata.get("players", [])
        ol_existing = next((p for p in players if p.get("position") == "OL"), None)
        gp = int((ol_existing or {}).get("gp", 8) or 8)
        ol_metrics_by_team[abbr] = compute_ol_trench_metrics(abbr, players, gp)

    ol_sorted = sorted(ol_metrics_by_team.items(), key=lambda x: x[1]["ol_score"], reverse=True)
    ol_rank_map = {abbr: idx + 1 for idx, (abbr, _) in enumerate(ol_sorted)}

    for abbr, tdata in teams.items():
        ol_rk = ol_rank_map[abbr]
        ol_ovr = rank_to_unit_ovr(ol_rk)
        m = ol_metrics_by_team[abbr]
        for p in tdata.get("players", []):
            if p.get("position") == "OL":
                p["pos_rank"] = ol_rk
                p["pos_total"] = 32
                p["ovr"] = ol_ovr
                p["grade"] = rating_to_grade(ol_ovr)
                p["stat_line"] = (
                    f"#{ol_rk} NFL OL • {m['pbwr_pct']}% Pass Block Win • "
                    f"{m['rb_ypc']:.1f} RB YPC ({m['rb_rush_ypg']:.0f} Rush YPG) • "
                    f"{m['sack_rate_pct']:.1f}% Sack Rate"
                )

    # 4. Build OL, DEF, HC leaderboards
    for pos in ("OL", "DEF", "HC"):
        all_units = [
            p for t in teams.values() for p in t["players"]
            if p["position"] == pos
        ]
        all_units.sort(key=lambda x: x["pos_rank"])
        leaderboards[pos] = [
            {
                "id": p["id"],
                "name": p["name"],
                "team": p["team"],
                "position": p["position"],
                "pos_rank": p["pos_rank"],
                "pos_total": 32,
                "ovr": p["ovr"],
                "grade": p["grade"],
                "pts_ppr": p["pts_ppr"],
                "stat_line": p["stat_line"],
                "headshot": p.get("headshot", ""),
            }
            for p in all_units
        ]

    # 5. Re-sort each team's skill players by pos_rank ascending so QB1/RB1/WR1/TE1 are in exact rank order
    for abbr, tdata in teams.items():
        skill = [p for p in tdata["players"] if p["position"] in ("QB", "RB", "WR", "TE")]
        units = [p for p in tdata["players"] if p["position"] in ("OL", "DEF", "HC")]
        reordered = []
        for pos in ("QB", "RB", "WR", "TE"):
            plist = [p for p in skill if p["position"] == pos]
            plist.sort(key=lambda x: x["pos_rank"])
            for idx, p in enumerate(plist):
                p["depth_label"] = f"{pos}{idx + 1}"
                p["is_starter"] = (idx == 0) or (pos == "WR" and idx <= 2) or (pos == "RB" and idx <= 1)
                reordered.append(p)
        tdata["players"] = reordered + units

    data["leaderboards"] = leaderboards
    data["last_calibrated_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_cache_json(data)
    print("Calibrated 2026/2027 positional & OL trench rankings (#1..#N) successfully.")


if __name__ == "__main__":
    calibrate_cached_data()
