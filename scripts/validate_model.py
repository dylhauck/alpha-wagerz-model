from pathlib import Path
import pandas as pd

from utils.json_utils import load_json

GAMES_DIR = Path("data/processed/games")
ALL_GAMES_FILE = Path("data/processed/all_games.json")
GAME_PROJECTIONS_FILE = Path("data/processed/game_projections.json")
MARKET_LINES_FILE = Path("data/processed/market_lines.json")

METRIC_FILES = [
    Path("data/processed/hitter_metrics_last_30_days.csv"),
    Path("data/processed/hitter_metrics_season.csv"),
    Path("data/processed/hitter_metrics_longterm.csv"),
]

REQUIRED_HITTER_FIELDS = [
    "Player",
    "Player ID",
    "Matchup",
    "Test Score",
    "Ceiling",
    "Zone Fit",
    "HR Form",
    "kHR",
    "Likely",
    "Confidence",
]

REQUIRED_MODEL_FIELDS = [
    "Power",
    "Contact",
    "Pitcher",
    "Pitch Type",
    "Team",
    "Bullpen",
    "Weather",
    "Park",
    "Recent",
]

REQUIRED_PITCHER_FIELDS = [
    "Team",
    "Pitcher",
    "Opponent",
    "Pitch Score",
    "Strikeout Score",
    "HR Vulnerability",
    "Fly Ball Profile",
    "Barrel Profile",
    "xwOBA",
    "CSW%",
    "SwStr%",
    "Ball%",
    "Brl/BIP%",
    "FB%",
    "GB%",
    "HH%",
    "K%",
    "BB%",
    "HR/9",
]

METRIC_RANGE_COLUMNS = [
    "ISO",
    "xwOBA",
    "xwOBAcon",
    "PulledBrl%",
    "Brl/BIP%",
    "Sweet Spot%",
    "FB%",
    "HH%",
    "LA",
    "SwStr%",
]

EXPECTED_RANGES = {
    "ISO": (0.000, 0.450),
    "xwOBA": (0.150, 0.600),
    "xwOBAcon": (0.200, 0.750),
    "PulledBrl%": (0.000, 20.000),
    "Brl/BIP%": (0.000, 28.000),
    "Sweet Spot%": (5.000, 60.000),
    "FB%": (5.000, 75.000),
    "HH%": (10.000, 75.000),
    "LA": (-20.000, 55.000),
    "SwStr%": (0.000, 35.000),
}


def f(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def has_missing(value):
    return value == "" or value is None


def pass_fail(condition):
    return "✅" if condition else "⚠️"


def validate_feature_completeness():
    missing_weather = []
    missing_hitter_fields = []
    missing_model_fields = []
    missing_pitcher_fields = []
    dome_games = []

    total_games = 0
    total_hitters = 0
    total_pitchers = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})
        if not game:
            continue

        total_games += 1

        game_name = game.get("game", file.name)
        weather = game.get("weather", {})
        roof = str(weather.get("roof") or game.get("roof") or "").lower()

        if not weather:
            missing_weather.append(game_name)

        if roof in ["dome", "closed", "retractable"]:
            dome_games.append(f"{game_name} — {roof}")

        hitters = game.get("hitters", {})
        if isinstance(hitters, dict):
            for side in ["away", "home"]:
                for hitter in hitters.get(side, []):
                    total_hitters += 1
                    player = hitter.get("Player", "")

                    for field in REQUIRED_HITTER_FIELDS:
                        if has_missing(hitter.get(field, "")):
                            missing_hitter_fields.append(f"{game_name}: {player} missing {field}")

                    for field in REQUIRED_MODEL_FIELDS:
                        if has_missing(hitter.get(field, "")):
                            missing_model_fields.append(f"{game_name}: {player} missing {field}")

        for pitcher in game.get("pitchers", []):
            pitcher_name = pitcher.get("Pitcher", "")

            if not pitcher_name or str(pitcher_name).upper() in ["TBD", "TBA"]:
                continue

            total_pitchers += 1

            for field in REQUIRED_PITCHER_FIELDS:
                if has_missing(pitcher.get(field, "")):
                    missing_pitcher_fields.append(f"{game_name}: {pitcher_name} missing {field}")

    print("\n🧪 Feature Completeness")
    print("=" * 56)
    print(f"Games checked: {total_games}")
    print(f"Hitters checked: {total_hitters}")
    print(f"Pitchers checked: {total_pitchers}")

    print(f"{pass_fail(not missing_weather)} Weather missing games: {len(missing_weather)}")
    print(f"{pass_fail(not missing_hitter_fields)} Hitter stat missing fields: {len(missing_hitter_fields)}")
    print(f"{pass_fail(not missing_model_fields)} Hitter model missing fields: {len(missing_model_fields)}")
    print(f"{pass_fail(not missing_pitcher_fields)} Pitcher missing fields: {len(missing_pitcher_fields)}")

    if dome_games:
        print("\n🏟️ Roof-controlled games:")
        for item in dome_games[:20]:
            print(f" - {item}")

    for title, items in [
        ("Missing weather", missing_weather),
        ("Missing hitter stat examples", missing_hitter_fields),
        ("Missing hitter model examples", missing_model_fields),
        ("Missing pitcher examples", missing_pitcher_fields),
    ]:
        if items:
            print(f"\n⚠️ {title}:")
            for item in items[:20]:
                print(f" - {item}")

    return {
        "missing_weather": len(missing_weather),
        "missing_hitter_fields": len(missing_hitter_fields),
        "missing_model_fields": len(missing_model_fields),
        "missing_pitcher_fields": len(missing_pitcher_fields),
    }


def validate_metric_ranges():
    print("\n📊 Hitter Metric Range Validation")
    print("=" * 56)

    issues = []

    for file in METRIC_FILES:
        if not file.exists():
            print(f"⚠️ Missing {file}")
            issues.append(f"Missing {file}")
            continue

        df = pd.read_csv(file)

        print()
        print(f"📁 {file}")
        print(f"Players: {len(df)}")

        if df.empty:
            issues.append(f"{file} is empty")
            continue

        for col in METRIC_RANGE_COLUMNS:
            if col not in df.columns:
                issues.append(f"{file} missing {col}")
                print(f"⚠️ {col:14} missing")
                continue

            values = pd.to_numeric(df[col], errors="coerce").dropna()

            if values.empty:
                issues.append(f"{file} has no numeric values for {col}")
                print(f"⚠️ {col:14} no numeric values")
                continue

            low, high = EXPECTED_RANGES[col]
            out_of_range = values[(values < low) | (values > high)]

            median = values.median()
            p75 = values.quantile(0.75)
            max_value = values.max()

            status = pass_fail(len(out_of_range) == 0)

            print(
                f"{status} {col:14} "
                f"min={values.min():.3f} "
                f"p25={values.quantile(.25):.3f} "
                f"median={median:.3f} "
                f"p75={p75:.3f} "
                f"max={max_value:.3f} "
                f"out={len(out_of_range)}"
            )

            if len(out_of_range):
                issues.append(f"{file} {col} has {len(out_of_range)} out-of-range values")

            # Warnings for metrics that are suspiciously low or compressed.
            if col == "Brl/BIP%" and p75 < 5:
                issues.append(f"{file} Brl/BIP% p75 looks too low: {p75:.2f}")
            if col == "PulledBrl%" and p75 < 2:
                issues.append(f"{file} PulledBrl% p75 looks too low: {p75:.2f}")
            if col == "xwOBAcon" and median < 0.300:
                issues.append(f"{file} xwOBAcon median looks too low: {median:.3f}")
            if col == "ISO" and median < 0.090:
                issues.append(f"{file} ISO median looks too low: {median:.3f}")

    if issues:
        print("\n⚠️ Metric warnings:")
        for issue in issues[:40]:
            print(f" - {issue}")
    else:
        print("\n✅ Metric ranges look sane.")

    return {"metric_issues": len(issues)}


def bucket_count(values, buckets):
    result = {label: 0 for label, _, _ in buckets}

    for value in values:
        num = f(value, None)
        if num is None:
            continue

        for label, low, high in buckets:
            if low <= num <= high:
                result[label] += 1
                break

    return result


def validate_score_distribution():
    games = load_json(ALL_GAMES_FILE, default=[])

    hitters = []
    for game in games:
        for side in ["away", "home"]:
            hitters.extend(game.get("hitters", {}).get(side, []))

    print("\n🔥 Score Distribution")
    print("=" * 56)

    if not hitters:
        print("⚠️ No hitters found in all_games.json")
        return {"distribution_issues": 1}

    issues = []

    for field in ["Likely", "Matchup", "Ceiling", "kHR", "HR Form"]:
        values = [h.get(field) for h in hitters if not has_missing(h.get(field))]
        nums = [f(v, None) for v in values]
        nums = [n for n in nums if n is not None]

        if not nums:
            print(f"⚠️ {field}: no values")
            issues.append(f"{field} no values")
            continue

        buckets = [
            ("90+", 90, 100),
            ("80-89", 80, 89.999),
            ("70-79", 70, 79.999),
            ("60-69", 60, 69.999),
            ("50-59", 50, 59.999),
            ("<50", -999, 49.999),
        ]

        counts = bucket_count(nums, buckets)
        print()
        print(f"{field}: min={min(nums):.1f} median={pd.Series(nums).median():.1f} max={max(nums):.1f}")
        for label, _, _ in buckets:
            print(f"  {label:6} {counts[label]}")

        if max(nums) < 75:
            issues.append(f"{field} max is too low/compressed: {max(nums):.1f}")
        if pd.Series(nums).median() < 45:
            issues.append(f"{field} median is very low: {pd.Series(nums).median():.1f}")

    if issues:
        print("\n⚠️ Distribution warnings:")
        for issue in issues:
            print(f" - {issue}")
    else:
        print("\n✅ Score distribution looks usable.")

    return {"distribution_issues": len(issues)}


def validate_market_and_projections():
    projections = load_json(GAME_PROJECTIONS_FILE, default=[])
    market_lines = load_json(MARKET_LINES_FILE, default=[])

    print("\n💰 Market + Projection Validation")
    print("=" * 56)

    if not projections:
        print("⚠️ No game projections found.")
        return {"projection_issues": 1}

    market_by_id = {str(m.get("game_id")): m for m in market_lines if m.get("game_id")}

    missing_market = []
    missing_moneyline = []
    missing_spread = []
    missing_total = []
    missing_team_totals = []
    missing_k_lines = []
    projection_math_issues = []

    for p in projections:
        game = p.get("game", p.get("game_id", "Unknown game"))
        game_id = str(p.get("game_id") or "")

        market = p.get("market") or market_by_id.get(game_id) or {}

        if not market:
            missing_market.append(game)
        if not market.get("moneyline", {}).get("away") or not market.get("moneyline", {}).get("home"):
            missing_moneyline.append(game)
        if market.get("spread", {}).get("away") is None or market.get("spread", {}).get("home") is None:
            missing_spread.append(game)
        if market.get("total") is None:
            missing_total.append(game)

        team_totals = market.get("team_totals", {})
        if team_totals.get("away") is None or team_totals.get("home") is None:
            missing_team_totals.append(game)

        away_pitcher = p.get("away_pitcher")
        home_pitcher = p.get("home_pitcher")

        if away_pitcher and away_pitcher not in ["TBD", "TBA"] and has_missing(p.get("away_pitcher_k_line")):
            missing_k_lines.append(f"{game}: {away_pitcher}")
        if home_pitcher and home_pitcher not in ["TBD", "TBA"] and has_missing(p.get("home_pitcher_k_line")):
            missing_k_lines.append(f"{game}: {home_pitcher}")

        away_runs = f(p.get("away_projected_runs"), None)
        home_runs = f(p.get("home_projected_runs"), None)
        total = f(p.get("projected_total"), None)

        if away_runs is not None and home_runs is not None and total is not None:
            if abs((away_runs + home_runs) - total) > 0.15:
                projection_math_issues.append(f"{game}: projected total mismatch")

        away_wp = f(p.get("away_win_probability"), None)
        home_wp = f(p.get("home_win_probability"), None)

        if away_wp is not None and home_wp is not None:
            if abs((away_wp + home_wp) - 100) > 1:
                projection_math_issues.append(f"{game}: win probability does not sum to 100")

    print(f"{pass_fail(not missing_market)} Games missing market object: {len(missing_market)}")
    print(f"{pass_fail(not missing_moneyline)} Games missing moneyline: {len(missing_moneyline)}")
    print(f"{pass_fail(not missing_spread)} Games missing spread: {len(missing_spread)}")
    print(f"{pass_fail(not missing_total)} Games missing game total: {len(missing_total)}")
    print(f"{pass_fail(not missing_team_totals)} Games missing team totals: {len(missing_team_totals)}")
    print(f"{pass_fail(not missing_k_lines)} Starters missing K lines: {len(missing_k_lines)}")
    print(f"{pass_fail(not projection_math_issues)} Projection math issues: {len(projection_math_issues)}")

    examples = [
        ("Missing market", missing_market),
        ("Missing moneyline", missing_moneyline),
        ("Missing spread", missing_spread),
        ("Missing total", missing_total),
        ("Missing team totals", missing_team_totals),
        ("Missing K lines", missing_k_lines),
        ("Projection math", projection_math_issues),
    ]

    for title, items in examples:
        if items:
            print(f"\n⚠️ {title} examples:")
            for item in items[:20]:
                print(f" - {item}")

    return {
        "missing_market": len(missing_market),
        "missing_moneyline": len(missing_moneyline),
        "missing_spread": len(missing_spread),
        "missing_total": len(missing_total),
        "missing_team_totals": len(missing_team_totals),
        "missing_k_lines": len(missing_k_lines),
        "projection_math_issues": len(projection_math_issues),
    }


def main():
    print("\n🐺 Alpha Wagerz Model QA Suite")
    print("=" * 56)

    results = {}
    results.update(validate_feature_completeness())
    results.update(validate_metric_ranges())
    results.update(validate_score_distribution())
    results.update(validate_market_and_projections())

    total_warnings = sum(value for value in results.values() if isinstance(value, int))

    print("\n📌 QA Summary")
    print("=" * 56)
    for key, value in results.items():
        print(f"{key}: {value}")

    if total_warnings:
        print(f"\n⚠️ QA finished with {total_warnings} warnings/items to review.")
    else:
        print("\n✅ QA finished clean.")


if __name__ == "__main__":
    main()
