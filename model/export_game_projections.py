from pathlib import Path
from providers import market
from utils.json_utils import load_json, save_json
from utils.player_name import normalize_player_name, player_last_name

ALL_GAMES_FILE = Path("data/processed/all_games.json")
MARKET_LINES_FILE = Path("data/processed/market_lines.json")
OUTPUT_FILE = Path("data/processed/game_projections.json")
K_LINES_OVERRIDE_FILE = Path("data/raw/k_lines_override.json")

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
    run_score = hitter_score * 0.45 + (100 - opp_pitch) * 0.25 + weather_score * 0.15 + park_score * 0.15
    return round(max(1.5, min(8.5, offense_runs(run_score))), 1)


def get_pitcher_for_team(game, team):
    return next((p for p in game.get("pitchers", []) if p.get("Team") == team), None)


def hitter_k_risk_score(hitters):
    if not hitters:
        return 50

    scores = []

    for h in hitters:
        swstr = f(h.get("SwStr%"), 10)
        khr = f(h.get("kHR"), 50)
        matchup = f(h.get("Matchup"), 50)

        score = (
            swstr * 3.0
            + khr * 0.45
            + matchup * 0.25
        )

        scores.append(score)

    return clamp(avg(scores, 50), 20, 90)


def projected_ks(pitcher, opponent_hitters):
    if not pitcher:
        return ""

    k_score = f(pitcher.get("Strikeout Score"), 50)
    swstr = f(pitcher.get("SwStr%"), 10)
    csw = f(pitcher.get("CSW%"), 28)
    ball = f(pitcher.get("Ball%"), 34)

    matchup_score = hitter_k_risk_score(opponent_hitters)

    ks = (
        3.2
        + ((k_score - 50) / 50) * 2.6
        + ((matchup_score - 50) / 50) * 3.0
        + ((swstr - 10) * 0.10)
        + ((csw - 28) * 0.07)
        - ((ball - 34) * 0.04)
    )

    return round(max(1.5, min(12.5, ks)), 1)


def win_probability(away_runs, home_runs):
    diff = away_runs - home_runs
    away_prob = clamp(50 + diff * 12, 5, 95)
    return round(away_prob), round(100 - away_prob)


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
    by_game_id, by_matchup = {}, {}
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
    return by_matchup.get(f"{norm(game.get('away_team'))}@{norm(game.get('home_team'))}", {})


def moneyline_analysis(away_team, home_team, away_wp, home_wp, market):
    moneyline = market.get("moneyline", {}) if market else {}
    away_ml, home_ml = moneyline.get("away"), moneyline.get("home")
    away_market_prob, home_market_prob = american_to_implied_prob(away_ml), american_to_implied_prob(home_ml)
    away_edge = None if away_market_prob is None else round(away_wp - away_market_prob, 1)
    home_edge = None if home_market_prob is None else round(home_wp - home_market_prob, 1)
    if away_edge is None and home_edge is None:
        lean = away_team if away_wp >= home_wp else home_team
        return {"moneyline_lean": lean, "moneyline_recommendation": f"{lean} ML", "moneyline_edge": "", "moneyline_confidence": "", "away_moneyline_edge": "", "home_moneyline_edge": ""}
    if (away_edge if away_edge is not None else -999) >= (home_edge if home_edge is not None else -999):
        lean, edge = away_team, away_edge
    else:
        lean, edge = home_team, home_edge
    return {"moneyline_lean": lean, "moneyline_recommendation": f"{lean} ML", "moneyline_edge": edge, "moneyline_confidence": confidence_from_edge(edge, 8), "away_moneyline_edge": away_edge if away_edge is not None else "", "home_moneyline_edge": home_edge if home_edge is not None else ""}


def format_spread(value):
    num = f(value, None)
    if num is None:
        return ""
    return f"+{num:g}" if num > 0 else f"{num:g}"


def spread_analysis(away_team, home_team, margin, market):
    spread = market.get("spread", {}) if market else {}
    away_line, home_line = spread.get("away"), spread.get("home")
    if away_line is None or home_line is None:
        team = away_team if margin > 0 else home_team
        return {"spread_lean": f"{team} spread lean", "spread_recommendation": f"{team} spread lean", "spread_edge": "", "spread_confidence": ""}
    away_edge = round(margin + f(away_line), 1)
    home_edge = round((-margin) + f(home_line), 1)
    if away_edge >= home_edge:
        lean, edge = f"{away_team} {format_spread(away_line)}", away_edge
    else:
        lean, edge = f"{home_team} {format_spread(home_line)}", home_edge
    return {"spread_lean": lean, "spread_recommendation": lean, "spread_edge": edge, "spread_confidence": confidence_from_edge(edge, 1.5), "away_spread_edge": away_edge, "home_spread_edge": home_edge}


def total_analysis(projected_total, market):
    total_line = market.get("total") if market else None
    if total_line is None:
        lean = "Over Lean" if projected_total >= 9.0 else "Under Lean" if projected_total <= 7.6 else "No Strong Total Lean"
        return {"total_lean": lean, "total_recommendation": lean, "total_edge": "", "total_confidence": ""}
    edge = round(projected_total - f(total_line), 1)
    lean = f"Over {total_line}" if edge > 0 else f"Under {total_line}" if edge < 0 else "No Strong Total Lean"
    return {"total_lean": lean, "total_recommendation": lean, "total_edge": edge, "total_confidence": confidence_from_edge(edge, 1.2)}


def team_total_analysis(away_team, home_team, away_runs, home_runs, market):
    team_totals = market.get("team_totals", {}) if market else {}
    away_line, home_line = team_totals.get("away"), team_totals.get("home")
    away_edge = "" if away_line is None else round(away_runs - f(away_line), 1)
    home_edge = "" if home_line is None else round(home_runs - f(home_line), 1)
    recs = []
    if away_edge != "": recs.append((abs(away_edge), f"{away_team} {'Over' if away_edge > 0 else 'Under'} {away_line}"))
    if home_edge != "": recs.append((abs(home_edge), f"{home_team} {'Over' if home_edge > 0 else 'Under'} {home_line}"))
    recs.sort(reverse=True, key=lambda x: x[0])
    return {"away_team_total_edge": away_edge, "home_team_total_edge": home_edge, "team_total_recommendation": recs[0][1] if recs else "No Team Total Lean", "team_total_confidence": confidence_from_edge(recs[0][0], 1.0) if recs else ""}


def prop_names_for_market(market):
    return [prop.get("player", key) for key, prop in (market.get("pitcher_strikeouts", {}) if market else {}).items()]


def find_pitcher_k_prop(pitcher_name, market):
    if not pitcher_name or str(pitcher_name).upper() in ["TBD", "TBA"] or not market:
        return None
    props = market.get("pitcher_strikeouts", {}) or {}
    if not props:
        return None
    target = normalize_player_name(pitcher_name)
    target_last = player_last_name(pitcher_name)
    if target in props:
        return props[target]
    for key, prop in props.items():
        for candidate in [key, prop.get("player", ""), prop.get("normalized_name", "")]:
            if normalize_player_name(candidate) == target:
                return prop
    target_parts = target.split()
    if len(target_parts) >= 2:
        target_first = target_parts[0]
        for key, prop in props.items():
            for candidate in [key, prop.get("player", ""), prop.get("normalized_name", "")]:
                parts = normalize_player_name(candidate).split()
                if len(parts) >= 2 and parts[0] == target_first and parts[-1] == target_last:
                    return prop
    if target_last:
        matches = []
        for key, prop in props.items():
            for candidate in [key, prop.get("player", ""), prop.get("normalized_name", "")]:
                if player_last_name(candidate) == target_last:
                    matches.append(prop); break
        if len(matches) == 1:
            return matches[0]
    return None

def get_manual_k_line(pitcher_name):
    overrides = load_json(K_LINES_OVERRIDE_FILE, default={})
    target = normalize_player_name(pitcher_name)

    for name, line in overrides.items():
        if normalize_player_name(name) == target:
            return line

    return ""

def find_pitcher_k_line(pitcher_name, market):
    prop = find_pitcher_k_prop(pitcher_name, market)

    if prop:
        return prop.get("line", "")

    manual_line = get_manual_k_line(pitcher_name)
    if manual_line != "":
        return manual_line

    return ""

def market_k_pitchers(market):
    props = market.get("pitcher_strikeouts", {}) if market else {}
    pitchers = []

    for key, prop in props.items():
        name = prop.get("player") or key
        line = prop.get("line", "")

        if name and line != "":
            pitchers.append({
                "name": name,
                "line": line,
                "prop": prop,
            })

    return pitchers


def get_market_k_pitchers(market):
    pitchers = market_k_pitchers(market)

    away = pitchers[0] if len(pitchers) >= 1 else None
    home = pitchers[1] if len(pitchers) >= 2 else None

    return away, home


def pitcher_k_analysis(projected, line):
    if line == "" or line is None:
        return {
            "edge": "",
            "recommendation": "K Line Missing",
            "confidence": "",
        }

    projected_num = f(projected)
    line_num = f(line)

    edge = round(projected_num - line_num, 1)

    return {
        "edge": edge,
        "recommendation": f"{'Over' if edge >= 0 else 'Under'} {line_num:g} Ks",
        "confidence": confidence_from_edge(edge, 1.2),
    }


def max_abs(*values):
    nums = [f(v, None) for v in values]
    nums = [v for v in nums if v is not None]
    return max(nums, key=lambda n: abs(n)) if nums else ""


def best_lean_from_projection(p):
    candidates = []
    for label, edge, confidence in [
        (p.get("moneyline_recommendation"), p.get("moneyline_edge"), p.get("moneyline_confidence")),
        (p.get("spread_recommendation"), p.get("spread_edge"), p.get("spread_confidence")),
        (p.get("total_recommendation"), p.get("total_edge"), p.get("total_confidence")),
        (p.get("team_total_recommendation"), max_abs(p.get("away_team_total_edge"), p.get("home_team_total_edge")), p.get("team_total_confidence")),
        (p.get("away_pitcher_k_recommendation"), p.get("away_pitcher_k_edge"), p.get("away_pitcher_k_confidence")),
        (p.get("home_pitcher_k_recommendation"), p.get("home_pitcher_k_edge"), p.get("home_pitcher_k_confidence")),
    ]:
        if label and edge != "" and edge is not None:
            candidates.append((f(confidence, 0), abs(f(edge, 0)), label))
    if not candidates:
        return p.get("moneyline_recommendation", "No Lean")
    candidates.sort(reverse=True)
    return candidates[0][2]


def get_game_hitters(game, side):
    hitters = game.get("hitters", {})

    if isinstance(hitters, dict):
        return hitters.get(side, [])

    if side == "away":
        return game.get("away_hitters", [])

    if side == "home":
        return game.get("home_hitters", [])

    return []

def export_game_projections():
    games = load_json(ALL_GAMES_FILE, default=[])
    market_by_game_id, market_by_matchup = get_market_lookup()

    output = []
    missing_k_props = []

    for game in games:
        away_team = game.get("away_team", "")
        home_team = game.get("home_team", "")

        away_hitters = get_game_hitters(game, "away")
        home_hitters = get_game_hitters(game, "home")

        away_pitcher = get_pitcher_for_team(game, away_team)
        home_pitcher = get_pitcher_for_team(game, home_team)

        weather_score = avg(
            [h.get("Weather") for h in away_hitters[:3] + home_hitters[:3]],
            50,
        )

        park_score = avg(
            [h.get("Park") for h in away_hitters[:3] + home_hitters[:3]],
            50,
        )

        away_runs = project_team_runs(
            away_hitters,
            home_pitcher,
            weather_score,
            park_score,
        )

        home_runs = project_team_runs(
            home_hitters,
            away_pitcher,
            weather_score,
            park_score,
        )

        total = round(away_runs + home_runs, 1)
        margin = round(away_runs - home_runs, 1)
        away_wp, home_wp = win_probability(away_runs, home_runs)

        market = find_market(game, market_by_game_id, market_by_matchup)

        moneyline = moneyline_analysis(away_team, home_team, away_wp, home_wp, market)
        spread = spread_analysis(away_team, home_team, margin, market)
        total_data = total_analysis(total, market)
        team_totals = team_total_analysis(
            away_team,
            home_team,
            away_runs,
            home_runs,
            market,
        )

        away_pitcher_name = away_pitcher.get("Pitcher", "TBD") if away_pitcher else "TBD"
        home_pitcher_name = home_pitcher.get("Pitcher", "TBD") if home_pitcher else "TBD"

        away_ks = projected_ks(away_pitcher, home_hitters)
        home_ks = projected_ks(home_pitcher, away_hitters)

        away_k_line = find_pitcher_k_line(away_pitcher_name, market)
        home_k_line = find_pitcher_k_line(home_pitcher_name, market)

        if market and away_pitcher_name not in ["TBD", "TBA"] and away_k_line == "":
            missing_k_props.append(
                f"{game.get('game')}: {away_pitcher_name} | available: "
                f"{', '.join(prop_names_for_market(market)) or 'none'}"
            )

        if market and home_pitcher_name not in ["TBD", "TBA"] and home_k_line == "":
            missing_k_props.append(
                f"{game.get('game')}: {home_pitcher_name} | available: "
                f"{', '.join(prop_names_for_market(market)) or 'none'}"
            )

        away_k = pitcher_k_analysis(away_ks, away_k_line)
        home_k = pitcher_k_analysis(home_ks, home_k_line)

        projection = {
            "game_id": game.get("game_id", ""),
            "game": game.get("game", ""),
            "game_time": game.get("game_time", ""),
            "game_time_sort": game.get("game_time_sort", ""),
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

            "away_pitcher_throws": away_pitcher.get("Throws", "") if away_pitcher else "",
            "home_pitcher_throws": home_pitcher.get("Throws", "") if home_pitcher else "",

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

    if missing_k_props:
        print(f"⚠️ Missing K props after normalization: {len(missing_k_props)}")
        for item in missing_k_props[:30]:
            print(f" - {item}")


if __name__ == "__main__":
    export_game_projections()
