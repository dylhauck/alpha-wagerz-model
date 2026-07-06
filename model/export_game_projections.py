from pathlib import Path
from utils.json_utils import load_json, save_json

ALL_GAMES_FILE = Path("data/processed/all_games.json")
MARKET_LINES_FILE = Path("data/processed/market_lines.json")
OUTPUT_FILE = Path("data/processed/game_projections.json")


def f(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def avg(values, default=50):
    nums = [f(v, None) for v in values]
    nums = [v for v in nums if v is not None]
    return sum(nums) / len(nums) if nums else default


def norm(value):
    return str(value or "").strip().lower().replace(".", "")


def top_hitters_score(hitters):
    top = sorted(hitters, key=lambda h: f(h.get("Likely")), reverse=True)[:5]
    return avg([h.get("Likely") for h in top], 50)


def pitcher_score(pitcher):
    if not pitcher:
        return 50

    strikeout = f(pitcher.get("Strikeout Score"), 50)
    pitch = f(pitcher.get("Pitch Score"), 50)
    hr_vuln = f(pitcher.get("HR Vulnerability"), 50)

    return clamp((pitch * 0.45) + (strikeout * 0.35) + ((100 - hr_vuln) * 0.20))


def offense_runs(score):
    return 3.2 + ((score - 50) / 50) * 2.8


def project_team_runs(team_hitters, opponent_pitcher, weather_score, park_score):
    hitter_score = top_hitters_score(team_hitters)
    opp_pitch = pitcher_score(opponent_pitcher)

    run_score = (
        hitter_score * 0.45
        + (100 - opp_pitch) * 0.25
        + weather_score * 0.15
        + park_score * 0.15
    )

    return round(max(1.5, min(8.5, offense_runs(run_score))), 1)


def get_pitcher_for_team(game, team):
    for pitcher in game.get("pitchers", []):
        if pitcher.get("Team") == team:
            return pitcher
    return None


def projected_ks(pitcher):
    if not pitcher:
        return ""

    k_score = f(pitcher.get("Strikeout Score"), 50)
    swstr = f(pitcher.get("SwStr%"), 10)
    csw = f(pitcher.get("CSW%"), 28)

    ks = 3.8 + ((k_score - 50) / 50) * 4.2 + ((swstr - 10) * 0.12) + ((csw - 28) * 0.08)
    return round(max(1.5, min(12.5, ks)), 1)


def win_probability(away_runs, home_runs):
    diff = away_runs - home_runs
    away_prob = clamp(50 + diff * 12, 5, 95)
    home_prob = 100 - away_prob
    return round(away_prob), round(home_prob)


def american_to_implied_prob(odds):
    odds = f(odds, None)
    if odds is None or odds == 0:
        return None

    if odds > 0:
        return 100 / (odds + 100) * 100

    return abs(odds) / (abs(odds) + 100) * 100


def confidence_from_edge(edge, scale=1.0):
    edge = abs(f(edge, 0))
    return round(clamp(50 + (edge / scale) * 25, 50, 95))


def get_market_lookup():
    lines = load_json(MARKET_LINES_FILE, default=[])
    by_game_id = {}
    by_matchup = {}

    for line in lines:
        game_id = str(line.get("game_id") or "")
        if game_id:
            by_game_id[game_id] = line

        away = norm(line.get("away_team"))
        home = norm(line.get("home_team"))
        if away and home:
            by_matchup[f"{away}@{home}"] = line

    return by_game_id, by_matchup


def find_market(game, by_game_id, by_matchup):
    game_id = str(game.get("game_id") or "")
    if game_id in by_game_id:
        return by_game_id[game_id]

    key = f"{norm(game.get('away_team'))}@{norm(game.get('home_team'))}"
    return by_matchup.get(key, {})


def moneyline_analysis(away_team, home_team, away_wp, home_wp, market):
    moneyline = market.get("moneyline", {}) if market else {}
    away_ml = moneyline.get("away")
    home_ml = moneyline.get("home")

    away_market_prob = american_to_implied_prob(away_ml)
    home_market_prob = american_to_implied_prob(home_ml)

    away_edge = None if away_market_prob is None else round(away_wp - away_market_prob, 1)
    home_edge = None if home_market_prob is None else round(home_wp - home_market_prob, 1)

    if away_edge is None and home_edge is None:
        lean = away_team if away_wp >= home_wp else home_team
        return {
            "moneyline_lean": lean,
            "moneyline_recommendation": f"{lean} ML",
            "moneyline_edge": "",
            "moneyline_confidence": "",
            "away_moneyline_edge": "",
            "home_moneyline_edge": "",
        }

    if (away_edge or -999) >= (home_edge or -999):
        lean = away_team
        edge = away_edge
    else:
        lean = home_team
        edge = home_edge

    return {
        "moneyline_lean": lean,
        "moneyline_recommendation": f"{lean} ML",
        "moneyline_edge": edge,
        "moneyline_confidence": confidence_from_edge(edge, 8),
        "away_moneyline_edge": away_edge if away_edge is not None else "",
        "home_moneyline_edge": home_edge if home_edge is not None else "",
    }


def spread_analysis(away_team, home_team, margin, market):
    spread = market.get("spread", {}) if market else {}
    away_line = spread.get("away")
    home_line = spread.get("home")

    if away_line is None or home_line is None:
        if margin > 0:
            return {
                "spread_lean": f"{away_team} spread lean",
                "spread_recommendation": f"{away_team} spread lean",
                "spread_edge": "",
                "spread_confidence": "",
            }
        return {
            "spread_lean": f"{home_team} spread lean",
            "spread_recommendation": f"{home_team} spread lean",
            "spread_edge": "",
            "spread_confidence": "",
        }

    # Away spread covers if away margin + away_line > 0.
    away_cover_margin = round(margin + f(away_line), 1)
    home_cover_margin = round((-margin) + f(home_line), 1)

    if away_cover_margin >= home_cover_margin:
        lean = f"{away_team} {format_spread(away_line)}"
        edge = away_cover_margin
    else:
        lean = f"{home_team} {format_spread(home_line)}"
        edge = home_cover_margin

    return {
        "spread_lean": lean,
        "spread_recommendation": lean,
        "spread_edge": edge,
        "spread_confidence": confidence_from_edge(edge, 1.5),
        "away_spread_edge": away_cover_margin,
        "home_spread_edge": home_cover_margin,
    }


def total_analysis(projected_total, market):
    total_line = market.get("total") if market else None

    if total_line is None:
        if projected_total >= 9.0:
            lean = "Over Lean"
        elif projected_total <= 7.6:
            lean = "Under Lean"
        else:
            lean = "No Strong Total Lean"

        return {
            "total_lean": lean,
            "total_recommendation": lean,
            "total_edge": "",
            "total_confidence": "",
        }

    edge = round(projected_total - f(total_line), 1)

    if edge > 0:
        lean = f"Over {total_line}"
    elif edge < 0:
        lean = f"Under {total_line}"
    else:
        lean = "No Strong Total Lean"

    return {
        "total_lean": lean,
        "total_recommendation": lean,
        "total_edge": edge,
        "total_confidence": confidence_from_edge(edge, 1.2),
    }


def team_total_analysis(away_team, home_team, away_runs, home_runs, market):
    team_totals = market.get("team_totals", {}) if market else {}
    away_line = team_totals.get("away")
    home_line = team_totals.get("home")

    away_edge = "" if away_line is None else round(away_runs - f(away_line), 1)
    home_edge = "" if home_line is None else round(home_runs - f(home_line), 1)

    recommendations = []

    if away_edge != "":
        recommendations.append((abs(away_edge), f"{away_team} {'Over' if away_edge > 0 else 'Under'} {away_line}"))

    if home_edge != "":
        recommendations.append((abs(home_edge), f"{home_team} {'Over' if home_edge > 0 else 'Under'} {home_line}"))

    recommendations.sort(reverse=True, key=lambda item: item[0])

    return {
        "away_team_total_edge": away_edge,
        "home_team_total_edge": home_edge,
        "team_total_recommendation": recommendations[0][1] if recommendations else "No Team Total Lean",
        "team_total_confidence": confidence_from_edge(recommendations[0][0], 1.0) if recommendations else "",
    }


def normalize_player_name(name):
    return norm(name).replace(" jr", "").replace(" sr", "")


def find_pitcher_k_line(pitcher_name, market):
    if not pitcher_name or pitcher_name == "TBD" or not market:
        return ""

    props = market.get("pitcher_strikeouts", {}) or {}
    target = normalize_player_name(pitcher_name)

    for player, prop in props.items():
        if normalize_player_name(player) == target:
            return prop.get("line", "")

    # Fuzzy fallback for first/last name mismatches.
    target_parts = set(target.split())
    for player, prop in props.items():
        player_parts = set(normalize_player_name(player).split())
        if target_parts and player_parts and len(target_parts.intersection(player_parts)) >= 2:
            return prop.get("line", "")

    return ""


def pitcher_k_analysis(projected, line):
    if line == "" or line is None:
        return {
            "edge": "",
            "recommendation": "No K Lean",
            "confidence": "",
        }

    edge = round(f(projected) - f(line), 1)
    recommendation = f"{'Over' if edge > 0 else 'Under'} {line} Ks"

    return {
        "edge": edge,
        "recommendation": recommendation,
        "confidence": confidence_from_edge(edge, 1.2),
    }


def format_spread(value):
    num = f(value, None)
    if num is None:
        return ""
    return f"+{num:g}" if num > 0 else f"{num:g}"


def best_lean_from_projection(projection):
    candidates = []

    for label, edge, confidence in [
        (projection.get("moneyline_recommendation"), projection.get("moneyline_edge"), projection.get("moneyline_confidence")),
        (projection.get("spread_recommendation"), projection.get("spread_edge"), projection.get("spread_confidence")),
        (projection.get("total_recommendation"), projection.get("total_edge"), projection.get("total_confidence")),
        (projection.get("team_total_recommendation"), max_abs(projection.get("away_team_total_edge"), projection.get("home_team_total_edge")), projection.get("team_total_confidence")),
        (projection.get("away_pitcher_k_recommendation"), projection.get("away_pitcher_k_edge"), projection.get("away_pitcher_k_confidence")),
        (projection.get("home_pitcher_k_recommendation"), projection.get("home_pitcher_k_edge"), projection.get("home_pitcher_k_confidence")),
    ]:
        if label and edge != "" and edge is not None:
            candidates.append((f(confidence, 0), abs(f(edge, 0)), label))

    if not candidates:
        return projection.get("moneyline_recommendation", "No Lean")

    candidates.sort(reverse=True)
    return candidates[0][2]


def max_abs(*values):
    nums = [f(v, None) for v in values]
    nums = [v for v in nums if v is not None]
    if not nums:
        return ""
    return max(nums, key=lambda n: abs(n))


def export_game_projections():
    games = load_json(ALL_GAMES_FILE, default=[])
    market_by_game_id, market_by_matchup = get_market_lookup()
    output = []

    for game in games:
        away_team = game.get("away_team", "")
        home_team = game.get("home_team", "")

        away_hitters = game.get("hitters", {}).get("away", [])
        home_hitters = game.get("hitters", {}).get("home", [])

        away_pitcher = get_pitcher_for_team(game, away_team)
        home_pitcher = get_pitcher_for_team(game, home_team)

        weather_score = avg([
            hitter.get("Weather")
            for hitter in away_hitters[:3] + home_hitters[:3]
        ], 50)

        park_score = avg([
            hitter.get("Park")
            for hitter in away_hitters[:3] + home_hitters[:3]
        ], 50)

        away_runs = project_team_runs(away_hitters, home_pitcher, weather_score, park_score)
        home_runs = project_team_runs(home_hitters, away_pitcher, weather_score, park_score)

        total = round(away_runs + home_runs, 1)
        margin = round(away_runs - home_runs, 1)
        away_wp, home_wp = win_probability(away_runs, home_runs)

        market = find_market(game, market_by_game_id, market_by_matchup)

        moneyline = moneyline_analysis(away_team, home_team, away_wp, home_wp, market)
        spread = spread_analysis(away_team, home_team, margin, market)
        total_data = total_analysis(total, market)
        team_totals = team_total_analysis(away_team, home_team, away_runs, home_runs, market)

        away_pitcher_name = away_pitcher.get("Pitcher", "TBD") if away_pitcher else "TBD"
        home_pitcher_name = home_pitcher.get("Pitcher", "TBD") if home_pitcher else "TBD"

        away_ks = projected_ks(away_pitcher)
        home_ks = projected_ks(home_pitcher)

        away_k_line = find_pitcher_k_line(away_pitcher_name, market)
        home_k_line = find_pitcher_k_line(home_pitcher_name, market)

        away_k = pitcher_k_analysis(away_ks, away_k_line)
        home_k = pitcher_k_analysis(home_ks, home_k_line)

        projection = {
            "game_id": game.get("game_id", ""),
            "game": game.get("game", ""),
            "game_time": game.get("game_time", ""),
            "venue": game.get("venue", ""),
            "away_team": away_team,
            "home_team": home_team,
            "away_projected_runs": away_runs,
            "home_projected_runs": home_runs,
            "projected_total": total,
            "projected_margin": margin,
            "away_win_probability": away_wp,
            "home_win_probability": home_wp,
            "market": market,
            "away_pitcher": away_pitcher_name,
            "home_pitcher": home_pitcher_name,
            "away_projected_ks": away_ks,
            "home_projected_ks": home_ks,
            "away_pitcher_k_line": away_k_line,
            "home_pitcher_k_line": home_k_line,
            "away_pitcher_k_edge": away_k["edge"],
            "home_pitcher_k_edge": home_k["edge"],
            "away_pitcher_k_recommendation": away_k["recommendation"],
            "home_pitcher_k_recommendation": home_k["recommendation"],
            "away_pitcher_k_confidence": away_k["confidence"],
            "home_pitcher_k_confidence": home_k["confidence"],
            **moneyline,
            **spread,
            **total_data,
            **team_totals,
        }

        projection["best_lean"] = best_lean_from_projection(projection)

        output.append(projection)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, OUTPUT_FILE)

    print(f"✅ Exported game projections for {len(output)} games")
    print(f"📁 {OUTPUT_FILE}")


if __name__ == "__main__":
    export_game_projections()
