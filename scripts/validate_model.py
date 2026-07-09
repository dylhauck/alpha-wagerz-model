from pathlib import Path
import pandas as pd
from utils.json_utils import load_json

ALL_GAMES_FILE = Path("data/processed/all_games.json")
GAME_PROJECTIONS_FILE = Path("data/processed/game_projections.json")
MARKET_LINES_FILE = Path("data/processed/market_lines.json")
METRIC_FILES = [Path("data/processed/hitter_metrics_last_30_days.csv"), Path("data/processed/hitter_metrics_season.csv"), Path("data/processed/hitter_metrics_longterm.csv")]
METRIC_RANGE_COLUMNS = ["ISO", "xwOBA", "xwOBAcon", "PulledBrl%", "Brl/BIP%", "Sweet Spot%", "FB%", "HH%", "LA", "SwStr%"]
EXPECTED_RANGES = {"ISO": (0, 2.1), "xwOBA": (0, .9), "xwOBAcon": (0, 2.1), "PulledBrl%": (0, 35), "Brl/BIP%": (0, 45), "Sweet Spot%": (0, 100), "FB%": (0, 100), "HH%": (0, 100), "LA": (-90, 90), "SwStr%": (0, 45)}


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


def metric_summary_for_file(file):
    if not file.exists():
        print(f"⚠️ Missing {file}")
        return [f"Missing {file}"]
    df = pd.read_csv(file)
    issues = []
    print(); print(f"📁 {file}"); print(f"Players: {len(df)}")
    qualified = df.copy()
    if "PA" in qualified.columns and "BIP" in qualified.columns:
        qualified = qualified[(pd.to_numeric(qualified["PA"], errors="coerce").fillna(0) >= 15) | (pd.to_numeric(qualified["BIP"], errors="coerce").fillna(0) >= 10)]
    print(f"Qualified-ish players: {len(qualified)}")
    for col in METRIC_RANGE_COLUMNS:
        if col not in df.columns:
            issues.append(f"{file} missing {col}"); print(f"⚠️ {col:14} missing"); continue
        values = pd.to_numeric(qualified[col], errors="coerce").dropna()
        if values.empty:
            issues.append(f"{file} has no qualified numeric values for {col}"); print(f"⚠️ {col:14} no qualified numeric values"); continue
        low, high = EXPECTED_RANGES[col]
        out = values[(values < low) | (values > high)]
        median, p75 = values.median(), values.quantile(.75)
        print(f"{pass_fail(len(out)==0)} {col:14} min={values.min():.3f} p25={values.quantile(.25):.3f} median={median:.3f} p75={p75:.3f} max={values.max():.3f} out={len(out)}")
        if len(out): issues.append(f"{file} {col} has {len(out)} out-of-range qualified values")
        if col == "Brl/BIP%" and p75 < 5: issues.append(f"{file} Brl/BIP% p75 looks too low: {p75:.2f}")
        if col == "PulledBrl%" and p75 < 2: issues.append(f"{file} PulledBrl% p75 looks too low: {p75:.2f}")
        if col == "xwOBAcon" and median < .250: issues.append(f"{file} xwOBAcon median looks too low: {median:.3f}")
        if col == "ISO" and median < .060: issues.append(f"{file} ISO median looks too low: {median:.3f}")
    return issues


def validate_metric_ranges():
    print("\n📊 Hitter Metric Range Validation"); print("="*56)
    issues = []
    for file in METRIC_FILES: issues.extend(metric_summary_for_file(file))
    if issues:
        print("\n⚠️ Metric warnings:")
        for issue in issues[:60]: print(f" - {issue}")
    else: print("\n✅ Metric ranges look sane.")
    return {"metric_issues": len(issues)}


def validate_score_distribution():
    games = load_json(ALL_GAMES_FILE, default=[])
    hitters = []
    for game in games:
        hitters_obj = game.get("hitters", {})

    if isinstance(hitters_obj, dict):
        for side in ["away", "home"]:
            hitters.extend(hitters_obj.get(side, []))
    elif isinstance(hitters_obj, list):
        hitters.extend(hitters_obj)
    print("\n🔥 Score Distribution"); print("="*56)
    issues = []
    if not hitters: print("⚠️ No hitters found in all_games.json"); return {"distribution_issues":1}
    for field in ["Likely", "Matchup", "Ceiling", "kHR", "HR Form"]:
        nums = [f(h.get(field), None) for h in hitters if not has_missing(h.get(field))]
        nums = [n for n in nums if n is not None]
        if not nums: issues.append(f"{field} no values"); print(f"⚠️ {field}: no values"); continue
        s = pd.Series(nums)
        print(f"{field}: min={min(nums):.1f} median={s.median():.1f} p75={s.quantile(.75):.1f} max={max(nums):.1f}")
        if max(nums) < 75: issues.append(f"{field} max is too low/compressed: {max(nums):.1f}")
    if issues:
        print("\n⚠️ Distribution warnings:")
        for issue in issues: print(f" - {issue}")
    else: print("\n✅ Score distribution looks usable.")
    return {"distribution_issues": len(issues)}


def validate_market_and_projections():
    projections = load_json(GAME_PROJECTIONS_FILE, default=[])
    market_lines = load_json(MARKET_LINES_FILE, default=[])
    print("\n💰 Market + Projection Validation"); print("="*56)
    if not projections: print("⚠️ No game projections found."); return {"projection_issues":1}
    market_by_id = {str(m.get("game_id")): m for m in market_lines if m.get("game_id")}
    missing_market, missing_moneyline, missing_spread, missing_total, missing_team_totals, missing_k_lines = [], [], [], [], [], []
    projection_math_issues = []
    for p in projections:
        game = p.get("game", p.get("game_id", "Unknown game")); game_id = str(p.get("game_id") or "")
        market = p.get("market") or market_by_id.get(game_id) or {}
        if not market: missing_market.append(game)
        if not market.get("moneyline", {}).get("away") or not market.get("moneyline", {}).get("home"): missing_moneyline.append(game)
        if market.get("spread", {}).get("away") is None or market.get("spread", {}).get("home") is None: missing_spread.append(game)
        if market.get("total") is None: missing_total.append(game)
        tt = market.get("team_totals", {})
        if tt.get("away") is None or tt.get("home") is None: missing_team_totals.append(game)
        if p.get("away_pitcher") not in ["TBD", "TBA", None, ""] and has_missing(p.get("away_pitcher_k_line")): missing_k_lines.append(f"{game}: {p.get('away_pitcher')}")
        if p.get("home_pitcher") not in ["TBD", "TBA", None, ""] and has_missing(p.get("home_pitcher_k_line")): missing_k_lines.append(f"{game}: {p.get('home_pitcher')}")
        ar, hr, total = f(p.get("away_projected_runs"), None), f(p.get("home_projected_runs"), None), f(p.get("projected_total"), None)
        if ar is not None and hr is not None and total is not None and abs((ar+hr)-total) > .15: projection_math_issues.append(f"{game}: projected total mismatch")
    print(f"{pass_fail(not missing_market)} Games missing market object: {len(missing_market)}")
    print(f"{pass_fail(not missing_moneyline)} Games missing moneyline: {len(missing_moneyline)}")
    print(f"{pass_fail(not missing_spread)} Games missing spread: {len(missing_spread)}")
    print(f"{pass_fail(not missing_total)} Games missing game total: {len(missing_total)}")
    print(f"{pass_fail(not missing_team_totals)} Games missing team totals: {len(missing_team_totals)}")
    print(f"{pass_fail(not missing_k_lines)} Starters missing K lines: {len(missing_k_lines)}")
    print(f"{pass_fail(not projection_math_issues)} Projection math issues: {len(projection_math_issues)}")
    for title, items in [("Missing market", missing_market), ("Missing moneyline", missing_moneyline), ("Missing spread", missing_spread), ("Missing total", missing_total), ("Missing team totals", missing_team_totals), ("Missing K lines", missing_k_lines), ("Projection math", projection_math_issues)]:
        if items:
            print(f"\n⚠️ {title} examples:")
            for item in items[:20]: print(f" - {item}")
    return {"missing_market":len(missing_market), "missing_moneyline":len(missing_moneyline), "missing_spread":len(missing_spread), "missing_total":len(missing_total), "missing_team_totals":len(missing_team_totals), "missing_k_lines":len(missing_k_lines), "projection_math_issues":len(projection_math_issues)}


def main():
    print("\n🐺 Alpha Wagerz Model QA Suite"); print("="*56)
    results = {}
    results.update(validate_metric_ranges()); results.update(validate_score_distribution()); results.update(validate_market_and_projections())
    total = sum(v for v in results.values() if isinstance(v, int))
    print("\n📌 QA Summary"); print("="*56)
    for k,v in results.items(): print(f"{k}: {v}")
    print(f"\n{'⚠️ QA finished with ' + str(total) + ' warnings/items to review.' if total else '✅ QA finished clean.'}")

if __name__ == "__main__": main()
