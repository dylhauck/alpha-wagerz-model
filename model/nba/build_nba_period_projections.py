from __future__ import annotations

import json
import math
import os
import statistics
import time

from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# PATHS / CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data" / "processed" / "nba"

SOURCE = DATA / "betting_projections.json"

OUT = DATA / "team_projections.json"

WEB = (
    ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nba"
    / "team_projections.json"
)

CACHE = DATA / "historical_quarters_2025-26.json"

SEASON = "2025-26"

MIN_TEAMS = 28

REQUEST_DELAY = 1.5

NBA_API_MAX_RETRIES = int(os.getenv('NBA_STATS_MAX_RETRIES', '3'))
NBA_API_TIMEOUT = int(os.getenv('NBA_STATS_TIMEOUT', '30'))
NBA_API_RETRY_DELAY = int(os.getenv('NBA_STATS_RETRY_DELAY', '5'))

# These are provisional assumptions, not empirically
# calibrated period-level standard deviations.
DEFAULT_MARGIN_SD = 8.0
DEFAULT_TOTAL_SD = 10.0


# ============================================================
# FILE HELPERS
# ============================================================

def write(path, obj):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            obj,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# HISTORICAL QUARTER DATA
# ============================================================

def load_history():
    """
    Fetch 2025-26 NBA quarter-level team averages.

    LeagueDashTeamStats provides aggregated team statistics,
    not individual game-by-game quarter observations.

    The resulting cache stores one scoring average and
    one points-allowed average for each team and quarter.
    """

    from nba_api.stats.endpoints import leaguedashteamstats
    from nba_api.stats.static import teams as nba_teams

    # --------------------------------------------------------
    # LOAD EXISTING CACHE
    # --------------------------------------------------------

    if CACHE.exists():
        try:
            cached = json.loads(
                CACHE.read_text(
                    encoding="utf-8"
                )
            )

            if (
                cached.get("season") == SEASON
                and cached.get("method") == "team_period_averages_v2"
                and isinstance(cached.get("teams"), dict)
                and len(cached["teams"]) >= MIN_TEAMS
            ):
                print(
                    f"Loaded cached NBA {SEASON} "
                    "quarter history.",
                    flush=True,
                )

                return cached["teams"]

        except (OSError, ValueError, TypeError):
            print(
                "Existing quarter cache is invalid. "
                "Fetching fresh data...",
                flush=True,
            )

    # --------------------------------------------------------
    # TEAM ID LOOKUP
    # --------------------------------------------------------

    team_id_map = {
        int(team["id"]): team["abbreviation"].upper()
        for team in nba_teams.get_teams()
    }

    teams = {}

    # --------------------------------------------------------
    # FETCH EACH QUARTER
    # --------------------------------------------------------

    for q in range(1, 5):
        print(
            f"Fetching NBA {SEASON} Q{q} history...",
            flush=True,
        )

        # Retry transient API failures without changing projection calculations.
        # Validate the response before accepting an attempt.
        df = None
        for attempt in range(1, NBA_API_MAX_RETRIES + 1):
            try:
                print(
                    f"NBA Q{q} API request "
                    f"(attempt {attempt}/{NBA_API_MAX_RETRIES})...",
                    flush=True,
                )

                endpoint = leaguedashteamstats.LeagueDashTeamStats(
                    season=SEASON,
                    season_type_all_star="Regular Season",
                    league_id_nullable="00",
                    period=q,
                    per_mode_detailed="PerGame",
                    timeout=NBA_API_TIMEOUT,
                )

                candidate = endpoint.get_data_frames()[0]
                if candidate.empty:
                    raise RuntimeError(f"NBA API returned no Q{q} team data.")

                required = {"TEAM_ID", "PTS"}
                missing = required - set(candidate.columns)
                if missing:
                    raise RuntimeError(
                        f"NBA API Q{q} response missing columns: "
                        f"{sorted(missing)}. Available columns: "
                        f"{list(candidate.columns)}"
                    )

                df = candidate
                print(f"NBA Q{q} API request successful.", flush=True)
                break

            except Exception as exc:
                print(
                    f"WARNING: NBA Q{q} request failed "
                    f"({attempt}/{NBA_API_MAX_RETRIES}): {exc}",
                    flush=True,
                )
                if attempt == NBA_API_MAX_RETRIES:
                    raise RuntimeError(
                        f"NBA Q{q} API failed after "
                        f"{NBA_API_MAX_RETRIES} attempts."
                    ) from exc
                wait_time = NBA_API_RETRY_DELAY * attempt
                print(f"Retrying in {wait_time} seconds...", flush=True)
                time.sleep(wait_time)

        if df is None:
            raise RuntimeError(f"Unable to retrieve NBA Q{q} statistics.")

        valid_count = 0

        for row in df.to_dict("records"):
            # ------------------------------------------------
            # RESOLVE TEAM ABBREVIATION
            # ------------------------------------------------

            try:
                team_id = int(row["TEAM_ID"])

                team = team_id_map.get(team_id)

                points = float(row["PTS"])

            except (TypeError, ValueError, KeyError):
                continue

            if not team:
                continue

            if not math.isfinite(points):
                continue

            # A typical NBA quarter team scoring average
            # should fall within a reasonable range.
            if not 15 <= points <= 40:
                continue

            entry = teams.setdefault(
                team,
                {
                    str(i): {
                        "for": [],
                        "against": [],
                    }
                    for i in range(1, 5)
                },
            )

            entry[str(q)]["for"] = [points]

            valid_count += 1

        print(
            f"Q{q}: validated {valid_count} teams.",
            flush=True,
        )

        if valid_count < MIN_TEAMS:
            raise RuntimeError(
                f"Only {valid_count} valid teams returned "
                f"for Q{q}. Refusing incomplete history."
            )

        time.sleep(REQUEST_DELAY)

    # --------------------------------------------------------
    # BUILD QUARTER POINTS-ALLOWED PROFILES
    # --------------------------------------------------------
    #
    # The endpoint response does not contain opponent
    # scoring directly.
    #
    # We therefore use the league scoring average as a
    # neutral defensive baseline.
    #
    # This is NOT equivalent to team-specific points allowed.
    # --------------------------------------------------------

    for q in range(1, 5):
        quarter = str(q)

        league_scores = [
            statistics.mean(
                data[quarter]["for"]
            )
            for data in teams.values()
            if data[quarter]["for"]
        ]

        if len(league_scores) < MIN_TEAMS:
            raise RuntimeError(
                f"Insufficient league scoring data "
                f"for Q{q}"
            )

        league_average = statistics.mean(
            league_scores
        )

        for data in teams.values():
            data[quarter]["against"] = [
                league_average
            ]

    # --------------------------------------------------------
    # VALIDATE COMPLETE TEAM HISTORY
    # --------------------------------------------------------

    valid = {
        team: data
        for team, data in teams.items()
        if all(
            data[str(q)]["for"]
            and data[str(q)]["against"]
            for q in range(1, 5)
        )
    }

    if len(valid) < MIN_TEAMS:
        raise RuntimeError(
            "Insufficient valid quarter history: "
            f"{len(valid)} teams"
        )

    # --------------------------------------------------------
    # SAVE CACHE
    # --------------------------------------------------------

    write(
        CACHE,
        {
            "season": SEASON,
            "method": "team_period_averages_v2",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "teams": valid,
        },
    )

    print(
        f"Saved historical quarter averages "
        f"for {len(valid)} NBA teams.",
        flush=True,
    )

    return valid


# ============================================================
# PROBABILITY HELPERS
# ============================================================

def normal_cdf(x):
    return 0.5 * (
        1.0 + math.erf(
            x / math.sqrt(2.0)
        )
    )


# ============================================================
# PERIOD PROJECTION
# ============================================================

def make_period(
    away,
    home,
    weights_a,
    weights_h,
    key,
    variance,
):
    # --------------------------------------------------------
    # PROJECTED SCORING
    # --------------------------------------------------------

    a = sum(
        away * weights_a[i]
        for i in key
    )

    h = sum(
        home * weights_h[i]
        for i in key
    )

    margin = h - a

    # --------------------------------------------------------
    # PROVISIONAL UNCERTAINTY
    # --------------------------------------------------------

    sigma_margin = (
        variance["margin"]
        * math.sqrt(len(key))
    )

    sigma_total = (
        variance["total"]
        * math.sqrt(len(key))
    )

    # --------------------------------------------------------
    # WIN PROBABILITY
    # --------------------------------------------------------

    hp = 100.0 * normal_cdf(
        margin / sigma_margin
    )

    hp = max(
        0.0,
        min(100.0, hp),
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    return {
        "away_score": round(a, 1),
        "home_score": round(h, 1),

        "projected_total": round(
            a + h,
            1,
        ),

        "home_margin": round(
            margin,
            1,
        ),

        "away_margin": round(
            -margin,
            1,
        ),

        "home_win_probability": round(
            hp,
            1,
        ),

        "away_win_probability": round(
            100.0 - hp,
            1,
        ),

        "home_spread": round(
            -margin,
            1,
        ),

        "away_spread": round(
            margin,
            1,
        ),

        "projected_winner": (
            "home"
            if margin >= 0
            else "away"
        ),

        "margin_sd": round(
            sigma_margin,
            2,
        ),

        "total_sd": round(
            sigma_total,
            2,
        ),

        "markets": None,
    }


# ============================================================
# TEAM QUARTER WEIGHTS
# ============================================================

def calculate_fractions(
    offense,
    opponent,
    history,
    league_weights,
):
    raw = []

    for q in range(1, 5):
        quarter = str(q)

        scoring = statistics.mean(
            history[offense][quarter]["for"]
        )

        allowed = statistics.mean(
            history[opponent][quarter]["against"]
        )

        raw.append(
            (scoring + allowed) / 2.0
        )

    total = sum(raw)

    if total <= 0:
        return list(league_weights)

    own = [
        value / total
        for value in raw
    ]

    weights = [
        0.75 * own[i]
        + 0.25 * league_weights[i]
        for i in range(4)
    ]

    # Normalize to guarantee that all four quarters
    # add back up to the original full-game projection.

    weight_sum = sum(weights)

    return [
        weight / weight_sum
        for weight in weights
    ]


# ============================================================
# MAIN BUILDER
# ============================================================

def main():
    # --------------------------------------------------------
    # LOAD EXISTING FULL-GAME PROJECTIONS
    # --------------------------------------------------------

    if not SOURCE.exists():
        raise FileNotFoundError(
            "Run the existing NBA model first: "
            f"{SOURCE}"
        )

    original = json.loads(
        SOURCE.read_text(
            encoding="utf-8"
        )
    )

    # --------------------------------------------------------
    # LOAD HISTORICAL QUARTER AVERAGES
    # --------------------------------------------------------

    history = load_history()

    # --------------------------------------------------------
    # LEAGUE QUARTER WEIGHTS
    # --------------------------------------------------------

    league_for = [
        statistics.mean(
            [
                statistics.mean(
                    team[str(q)]["for"]
                )
                for team in history.values()
            ]
        )
        for q in range(1, 5)
    ]

    league_sum = sum(
        league_for
    )

    if league_sum <= 0:
        raise RuntimeError(
            "Invalid league quarter scoring totals."
        )

    league_weights = [
        value / league_sum
        for value in league_for
    ]

    # --------------------------------------------------------
    # BUILD GAME PROJECTIONS
    # --------------------------------------------------------

    games = []

    for game in original.get("games", []):
        away_team = str(
            game["away_team"]
        ).upper()

        home_team = str(
            game["home_team"]
        ).upper()

        model = game["model"]

        # Preserve existing game fields, excluding
        # player projections as in the original builder.

        result = {
            key: value
            for key, value in game.items()
            if key != "player_projections"
        }

        result["periods"] = {}

        # ----------------------------------------------------
        # VERIFY TEAM HISTORY
        # ----------------------------------------------------

        if (
            away_team not in history
            or home_team not in history
        ):
            result["periods_status"] = (
                "unavailable: historical "
                "quarter splits missing"
            )

            games.append(result)
            continue

        # ----------------------------------------------------
        # READ FULL-GAME MODEL SCORES
        # ----------------------------------------------------

        away_score = float(
            model["away_score"]
        )

        home_score = float(
            model["home_score"]
        )

        # ----------------------------------------------------
        # CALCULATE QUARTER SCORING WEIGHTS
        # ----------------------------------------------------

        away_weights = calculate_fractions(
            away_team,
            home_team,
            history,
            league_weights,
        )

        home_weights = calculate_fractions(
            home_team,
            away_team,
            history,
            league_weights,
        )

        # ----------------------------------------------------
        # PROVISIONAL VARIANCE ASSUMPTIONS
        # ----------------------------------------------------

        variance = {
            "margin": DEFAULT_MARGIN_SD,
            "total": DEFAULT_TOTAL_SD,
        }

        # ----------------------------------------------------
        # QUARTER / HALF MAPPING
        # ----------------------------------------------------

        mapping = {
            "Q1": (0,),
            "Q2": (1,),
            "Q3": (2,),
            "Q4": (3,),
            "1H": (0, 1),
            "2H": (2, 3),
        }

        # ----------------------------------------------------
        # GENERATE PERIODS
        # ----------------------------------------------------

        for name, keys in mapping.items():
            result["periods"][name] = make_period(
                away_score,
                home_score,
                away_weights,
                home_weights,
                keys,
                variance,
            )

        result["periods_status"] = (
            "Estimated from 2025-26 historical "
            "quarter scoring averages; "
            "probabilities not backtested"
        )

        games.append(result)

        print(
            f"Built NBA period projections: "
            f"{away_team} @ {home_team}",
            flush=True,
        )

    # --------------------------------------------------------
    # FINAL OUTPUT
    # --------------------------------------------------------

    output = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "slate_date": original.get(
            "slate_date"
        ),

        "season": original.get(
            "season"
        ),

        "game_count": len(games),

        "period_methodology": (
            "Historical 2025-26 NBA quarter "
            "scoring averages redistribute "
            "existing full-game model totals. "
            "Opponent defensive quarter "
            "scoring uses a neutral league "
            "baseline. Win probabilities "
            "use assumed normal-distribution "
            "uncertainty and are not backtested."
        ),

        "games": games,
    }

    # --------------------------------------------------------
    # SAVE MODEL OUTPUT
    # --------------------------------------------------------

    write(
        OUT,
        output,
    )

    # --------------------------------------------------------
    # SAVE WEBSITE OUTPUT
    # --------------------------------------------------------

    try:
        write(
            WEB,
            output,
        )

        print(
            f"Saved web copy: {WEB}",
            flush=True,
        )

    except OSError as exc:
        print(
            f"Web copy not written: {exc}",
            flush=True,
        )

    print(
        f"Saved {len(games)} NBA projections "
        f"to {OUT}",
        flush=True,
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()