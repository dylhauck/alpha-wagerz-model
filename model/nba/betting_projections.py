from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = ROOT / "data" / "processed" / "nba"
WEB_DIR = ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nba"

SLATE_PATH = PROCESSED_DIR / "slate.json"
TEAM_STATS_PATH = PROCESSED_DIR / "team_stats.json"
TEAM_RANKINGS_PATH = PROCESSED_DIR / "team_rankings.json"
PLAYER_STATS_PATH = PROCESSED_DIR / "player_stats.json"
PLAYER_MATCHUPS_PATH = PROCESSED_DIR / "player_matchups.json"

OUTPUT_PATH = PROCESSED_DIR / "betting_projections.json"
WEB_OUTPUT_PATH = WEB_DIR / "betting_projections.json"


# ============================================================
# MODEL CONFIG
# ============================================================

# Current-season data gradually takes over from last-season data.
#
# 0 games  -> 0% current / 100% previous
# 5 games  -> 25% current / 75% previous
# 10 games -> 50% current / 50% previous
# 15 games -> 75% current / 25% previous
# 20 games -> 100% current
CURRENT_SEASON_FULL_WEIGHT_GAMES = 20

# NBA home-court advantage expressed in points.
HOME_COURT_ADVANTAGE = 2.2

# Dampens extreme projections toward league average.
REGRESSION_TO_LEAGUE = 0.12

# Used to convert projected scoring margin into a win probability.
WIN_PROBABILITY_SCALE = 11.0

# Player sample thresholds.
PLAYER_CURRENT_FULL_WEIGHT_GAMES = 20
PLAYER_MIN_MINUTES = 4.0

# Number of player projections retained for each team/game.
MAX_PLAYER_PROJECTIONS_PER_TEAM = 15


# ============================================================
# BASIC HELPERS
# ============================================================

def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required NBA data file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")

    return data


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _round(value: float, digits: int = 1) -> float:
    return round(float(value), digits)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _weighted_average(
    current_value: float,
    previous_value: float,
    current_games: int,
    full_weight_games: int = CURRENT_SEASON_FULL_WEIGHT_GAMES,
) -> Tuple[float, float, float]:
    """
    Returns:
        blended_value,
        current_weight,
        previous_weight
    """

    if current_games <= 0:
        return previous_value, 0.0, 1.0

    current_weight = _clamp(
        current_games / float(full_weight_games),
        0.0,
        1.0,
    )

    previous_weight = 1.0 - current_weight

    blended = (
        current_value * current_weight
        + previous_value * previous_weight
    )

    return blended, current_weight, previous_weight


# ============================================================
# TEAM DATA
# ============================================================

def _index_team_stats(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}

    for team in payload.get("teams", []):
        abbr = str(team.get("team") or "").upper().strip()

        if abbr:
            indexed[abbr] = team

    return indexed


def _index_team_rankings(
    payload: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}

    for team in payload.get("teams", []):
        abbr = str(team.get("team") or "").upper().strip()

        if abbr:
            indexed[abbr] = team

    return indexed


def _league_baseline(
    team_stats: Dict[str, Dict[str, Any]],
) -> Dict[str, float]:
    """
    Builds the league scoring baseline from usable team seasons.

    Early in a new season this naturally uses last-season numbers.
    Later it blends current and last-season numbers team-by-team.
    """

    points_for: List[float] = []
    points_against: List[float] = []
    rebounds: List[float] = []
    assists: List[float] = []
    turnovers: List[float] = []
    threes: List[float] = []

    for team in team_stats.values():
        current = team.get("current_season") or {}
        previous = team.get("last_season") or {}

        current_games = _safe_int(current.get("games"))
        previous_games = _safe_int(previous.get("games"))

        current_pg = current.get("per_game") or {}
        previous_pg = previous.get("per_game") or {}

        if current_games <= 0 and previous_games <= 0:
            continue

        def blended_stat(key: str) -> float:
            current_value = _safe_float(current_pg.get(key))
            previous_value = _safe_float(previous_pg.get(key))

            value, _, _ = _weighted_average(
                current_value,
                previous_value,
                current_games,
            )

            return value

        points_for.append(blended_stat("pts"))
        points_against.append(blended_stat("pts_allowed"))
        rebounds.append(blended_stat("reb"))
        assists.append(blended_stat("ast"))
        turnovers.append(blended_stat("tov"))
        threes.append(blended_stat("fg3m"))

    def avg(values: List[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    avg_for = avg(points_for)
    avg_against = avg(points_against)

    scoring = (
        (avg_for + avg_against) / 2.0
        if avg_for and avg_against
        else avg_for or avg_against
    )

    return {
        "points": scoring,
        "points_for": avg_for,
        "points_against": avg_against,
        "rebounds": avg(rebounds),
        "assists": avg(assists),
        "turnovers": avg(turnovers),
        "threes": avg(threes),
    }


def _build_team_profile(
    team: Dict[str, Any],
    league: Dict[str, float],
) -> Dict[str, Any]:
    current = team.get("current_season") or {}
    previous = team.get("last_season") or {}

    current_games = _safe_int(current.get("games"))
    previous_games = _safe_int(previous.get("games"))

    current_pg = current.get("per_game") or {}
    previous_pg = previous.get("per_game") or {}

    current_pct = current.get("percentages") or {}
    previous_pct = previous.get("percentages") or {}

    def blended_pg(key: str) -> float:
        value, _, _ = _weighted_average(
            _safe_float(current_pg.get(key)),
            _safe_float(previous_pg.get(key)),
            current_games,
        )
        return value

    def blended_pct(key: str) -> float:
        value, _, _ = _weighted_average(
            _safe_float(current_pct.get(key)),
            _safe_float(previous_pct.get(key)),
            current_games,
        )
        return value

    _, current_weight, previous_weight = _weighted_average(
        0.0,
        0.0,
        current_games,
    )

    pts = blended_pg("pts")
    pts_allowed = blended_pg("pts_allowed")
    point_diff = blended_pg("point_diff")
    reb = blended_pg("reb")
    ast = blended_pg("ast")
    tov = blended_pg("tov")
    fg3m = blended_pg("fg3m")

    league_points = league.get("points") or 0.0

    offense_index = (
        pts / league_points
        if league_points > 0
        else 1.0
    )

    defense_index = (
        pts_allowed / league_points
        if league_points > 0
        else 1.0
    )

    return {
        "team": team.get("team"),
        "team_name": team.get("team_name"),
        "conference": team.get("conference"),
        "games": {
            "current": current_games,
            "previous": previous_games,
        },
        "weights": {
            "current_season": _round(current_weight, 3),
            "last_season": _round(previous_weight, 3),
        },
        "per_game": {
            "pts": _round(pts, 2),
            "pts_allowed": _round(pts_allowed, 2),
            "point_diff": _round(point_diff, 2),
            "reb": _round(reb, 2),
            "ast": _round(ast, 2),
            "tov": _round(tov, 2),
            "fg3m": _round(fg3m, 2),
        },
        "percentages": {
            "fg_pct": _round(blended_pct("fg_pct"), 3),
            "fg3_pct": _round(blended_pct("fg3_pct"), 3),
            "ft_pct": _round(blended_pct("ft_pct"), 3),
        },
        "ratings": {
            "offense_index": _round(offense_index, 4),
            "defense_index": _round(defense_index, 4),
        },
    }


# ============================================================
# PLAYER DATA
# ============================================================

def _index_player_stats(
    payload: Dict[str, Any],
) -> Dict[int, Dict[str, Any]]:
    indexed: Dict[int, Dict[str, Any]] = {}

    for player in payload.get("players", []):
        player_id = _safe_int(player.get("player_id"))

        if player_id:
            indexed[player_id] = player

    return indexed


def _index_matchup_games(
    payload: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}

    for game in payload.get("games", []):
        game_id = str(game.get("game_id") or "").strip()

        if game_id:
            indexed[game_id] = game

    return indexed


def _player_projection(
    player: Dict[str, Any],
    matchup_player: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Produces a baseline player projection.

    This intentionally does NOT manufacture sportsbook props.

    It provides model-side expected production which can later be
    compared against real sportsbook prop lines.
    """

    current = player.get("current_season") or {}
    previous = player.get("last_season") or {}

    current_games = _safe_int(current.get("games"))
    previous_games = _safe_int(previous.get("games"))

    current_pg = current.get("per_game") or {}
    previous_pg = previous.get("per_game") or {}

    if current_games <= 0 and previous_games <= 0:
        return None

    def blend(key: str) -> float:
        value, _, _ = _weighted_average(
            _safe_float(current_pg.get(key)),
            _safe_float(previous_pg.get(key)),
            current_games,
            PLAYER_CURRENT_FULL_WEIGHT_GAMES,
        )
        return value

    minutes = blend("min")

    # Player matchup splits may contain a more matchup-specific
    # historical baseline.
    matchup_last = {}

    if matchup_player:
        splits = matchup_player.get("splits") or {}
        matchup_last = splits.get("last_season") or {}

    matchup_games = _safe_int(matchup_last.get("games"))

    # Small matchup samples are intentionally weighted lightly.
    matchup_weight = _clamp(matchup_games / 10.0, 0.0, 0.25)

    def matchup_adjusted(
        normal_key: str,
        matchup_key: str,
    ) -> float:
        base = blend(normal_key)

        if matchup_games <= 0:
            return base

        matchup_value = _safe_float(
            matchup_last.get(matchup_key),
            base,
        )

        return (
            base * (1.0 - matchup_weight)
            + matchup_value * matchup_weight
        )

    pts = matchup_adjusted("pts", "pts_per_game")
    reb = matchup_adjusted("reb", "reb_per_game")
    ast = matchup_adjusted("ast", "ast_per_game")
    stl = matchup_adjusted("stl", "stl_per_game")
    blk = matchup_adjusted("blk", "blk_per_game")
    tov = matchup_adjusted("tov", "tov_per_game")
    fg3m = matchup_adjusted("fg3m", "fg3m_per_game")

    _, current_weight, previous_weight = _weighted_average(
        0.0,
        0.0,
        current_games,
        PLAYER_CURRENT_FULL_WEIGHT_GAMES,
    )

    return {
        "player_id": player.get("player_id"),
        "player_name": player.get("player_name"),
        "team": player.get("team"),
        "position": player.get("position"),
        "position_group": player.get("position_group"),
        "number": player.get("number"),
        "games": {
            "current": current_games,
            "last_season": previous_games,
            "matchup_last_season": matchup_games,
        },
        "weights": {
            "current_season": _round(current_weight, 3),
            "last_season": _round(previous_weight, 3),
            "matchup": _round(matchup_weight, 3),
        },
        "projection": {
            "min": _round(minutes, 1),
            "pts": _round(pts, 1),
            "reb": _round(reb, 1),
            "ast": _round(ast, 1),
            "stl": _round(stl, 1),
            "blk": _round(blk, 1),
            "tov": _round(tov, 1),
            "fg3m": _round(fg3m, 1),
            "pra": _round(pts + reb + ast, 1),
            "pr": _round(pts + reb, 1),
            "pa": _round(pts + ast, 1),
            "ra": _round(reb + ast, 1),
        },
    }


def _game_player_projections(
    game_id: str,
    away_team: str,
    home_team: str,
    player_stats: Dict[int, Dict[str, Any]],
    matchup_games: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    matchup_game = matchup_games.get(game_id) or {}

    matchup_by_id: Dict[int, Dict[str, Any]] = {}

    for key in ("away_players", "home_players"):
        for player in matchup_game.get(key, []):
            player_id = _safe_int(player.get("player_id"))

            if player_id:
                matchup_by_id[player_id] = player

    results: Dict[str, List[Dict[str, Any]]] = {
        "away": [],
        "home": [],
    }

    for player_id, player in player_stats.items():
        team = str(player.get("team") or "").upper()

        if team not in {away_team, home_team}:
            continue

        projection = _player_projection(
            player,
            matchup_by_id.get(player_id),
        )

        if not projection:
            continue

        projected_minutes = _safe_float(
            projection.get("projection", {}).get("min")
        )

        if projected_minutes < PLAYER_MIN_MINUTES:
            continue

        side = "away" if team == away_team else "home"
        results[side].append(projection)

    for side in ("away", "home"):
        results[side].sort(
            key=lambda x: (
                _safe_float(
                    x.get("projection", {}).get("min")
                ),
                _safe_float(
                    x.get("projection", {}).get("pts")
                ),
            ),
            reverse=True,
        )

        results[side] = results[side][
            :MAX_PLAYER_PROJECTIONS_PER_TEAM
        ]

    return results


# ============================================================
# GAME MODEL
# ============================================================

def _project_team_score(
    offense: Dict[str, Any],
    defense: Dict[str, Any],
    league_points: float,
) -> float:
    """
    Basic opponent-adjusted scoring model.

    Example:
        Team scores 115
        Opponent allows 110
        League average is 112

    Both offensive and defensive quality contribute to the expected
    scoring level.
    """

    offense_pts = _safe_float(
        offense.get("per_game", {}).get("pts"),
        league_points,
    )

    opponent_allowed = _safe_float(
        defense.get("per_game", {}).get("pts_allowed"),
        league_points,
    )

    if league_points <= 0:
        return (offense_pts + opponent_allowed) / 2.0

    offense_factor = offense_pts / league_points
    defense_factor = opponent_allowed / league_points

    expected = league_points * offense_factor * defense_factor

    # Pull extreme values slightly toward league average.
    expected = (
        expected * (1.0 - REGRESSION_TO_LEAGUE)
        + league_points * REGRESSION_TO_LEAGUE
    )

    return expected


def _win_probability(home_margin: float) -> float:
    """
    Logistic conversion from projected home scoring margin
    to home win probability.
    """

    probability = 1.0 / (
        1.0
        + math.exp(
            -home_margin / WIN_PROBABILITY_SCALE
        )
    )

    return _clamp(probability, 0.01, 0.99)


def _model_confidence(
    away_profile: Dict[str, Any],
    home_profile: Dict[str, Any],
) -> float:
    """
    Confidence reflects how much current-season information exists.

    This is NOT a betting-edge confidence rating yet.
    """

    away_current = _safe_int(
        away_profile.get("games", {}).get("current")
    )

    home_current = _safe_int(
        home_profile.get("games", {}).get("current")
    )

    average_current_games = (
        away_current + home_current
    ) / 2.0

    season_progress = _clamp(
        average_current_games
        / CURRENT_SEASON_FULL_WEIGHT_GAMES,
        0.0,
        1.0,
    )

    # We still have a full previous-season baseline, so confidence
    # starts above zero even on opening night.
    confidence = 0.55 + (season_progress * 0.35)

    return _clamp(confidence, 0.0, 0.90)


def _project_game(
    game: Dict[str, Any],
    team_stats: Dict[str, Dict[str, Any]],
    team_rankings: Dict[str, Dict[str, Any]],
    league: Dict[str, float],
    player_stats: Dict[int, Dict[str, Any]],
    matchup_games: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    game_id = str(game.get("game_id") or "")

    away_team = str(
        game.get("away_abbr")
        or game.get("away_team")
        or ""
    ).upper()

    home_team = str(
        game.get("home_abbr")
        or game.get("home_team")
        or ""
    ).upper()

    away_raw = team_stats.get(away_team)
    home_raw = team_stats.get(home_team)

    if not away_raw:
        raise ValueError(
            f"No team_stats entry found for away team {away_team}"
        )

    if not home_raw:
        raise ValueError(
            f"No team_stats entry found for home team {home_team}"
        )

    away_profile = _build_team_profile(
        away_raw,
        league,
    )

    home_profile = _build_team_profile(
        home_raw,
        league,
    )

    league_points = league.get("points") or 0.0

    away_score = _project_team_score(
        away_profile,
        home_profile,
        league_points,
    )

    home_score = _project_team_score(
        home_profile,
        away_profile,
        league_points,
    )

    # Apply home court as a symmetric adjustment so the total does
    # not artificially increase just because one team is at home.
    half_hca = HOME_COURT_ADVANTAGE / 2.0

    home_score += half_hca
    away_score -= half_hca

    projected_total = away_score + home_score
    home_margin = home_score - away_score
    away_margin = -home_margin

    home_win_probability = _win_probability(home_margin)
    away_win_probability = 1.0 - home_win_probability

    players = _game_player_projections(
        game_id,
        away_team,
        home_team,
        player_stats,
        matchup_games,
    )

    away_ranking = team_rankings.get(away_team) or {}
    home_ranking = team_rankings.get(home_team) or {}

    confidence = _model_confidence(
        away_profile,
        home_profile,
    )

    projected_winner = (
        home_team
        if home_score >= away_score
        else away_team
    )

    return {
        "game_id": game_id,
        "season": game.get("season"),
        "game_type": game.get("game_type"),
        "game_date": game.get("game_date"),
        "game_time": game.get("game_time"),
        "game_datetime": game.get("game_datetime"),
        "game_datetime_utc": game.get("game_datetime_utc"),
        "status": game.get("status"),
        "status_code": game.get("status_code"),
        "venue": game.get("venue"),
        "arena": game.get("arena"),
        "arena_city": game.get("arena_city"),
        "arena_state": game.get("arena_state"),
        "week_number": game.get("week_number"),
        "week_name": game.get("week_name"),
        "away_team": away_team,
        "home_team": home_team,
        "away_record": game.get("away_record"),
        "home_record": game.get("home_record"),
        "model": {
            "away_score": _round(away_score, 1),
            "home_score": _round(home_score, 1),
            "projected_total": _round(projected_total, 1),
            "home_margin": _round(home_margin, 1),
            "away_margin": _round(away_margin, 1),
            "projected_winner": projected_winner,
            "away_win_probability": _round(
                away_win_probability * 100.0,
                1,
            ),
            "home_win_probability": _round(
                home_win_probability * 100.0,
                1,
            ),
            "confidence": _round(
                confidence * 100.0,
                1,
            ),
        },
        "team_profiles": {
            "away": away_profile,
            "home": home_profile,
        },
        "standings": {
            "away": away_ranking.get("standings"),
            "home": home_ranking.get("standings"),
        },
        "player_projections": players,

        # These sections intentionally remain unavailable until
        # real current sportsbook lines are connected.
        #
        # We will NOT manufacture market prices or betting edges.
        "markets": {
            "moneyline": None,
            "spread": None,
            "total": None,
            "team_totals": None,
            "quarters": None,
            "first_basket": None,
            "player_props": None,
        },
        "edges": [],
        "best_bets": [],
    }


# ============================================================
# BUILD
# ============================================================

def build_nba_betting_projections() -> Dict[str, Any]:
    print("Loading NBA projection inputs...", flush=True)

    slate = _load_json(SLATE_PATH)
    team_stats_payload = _load_json(TEAM_STATS_PATH)
    team_rankings_payload = _load_json(TEAM_RANKINGS_PATH)
    player_stats_payload = _load_json(PLAYER_STATS_PATH)
    player_matchups_payload = _load_json(PLAYER_MATCHUPS_PATH)

    team_stats = _index_team_stats(team_stats_payload)
    team_rankings = _index_team_rankings(
        team_rankings_payload
    )

    player_stats = _index_player_stats(
        player_stats_payload
    )

    matchup_games = _index_matchup_games(
        player_matchups_payload
    )

    league = _league_baseline(team_stats)

    games: List[Dict[str, Any]] = []

    slate_games = slate.get("games", [])

    print(
        f"Projecting {len(slate_games)} NBA games...",
        flush=True,
    )

    for game in slate_games:
        try:
            projection = _project_game(
                game=game,
                team_stats=team_stats,
                team_rankings=team_rankings,
                league=league,
                player_stats=player_stats,
                matchup_games=matchup_games,
            )

            games.append(projection)

            model = projection["model"]

            print(
                f"  {projection['away_team']} @ "
                f"{projection['home_team']} -> "
                f"{model['away_score']} - "
                f"{model['home_score']} "
                f"(Total {model['projected_total']})",
                flush=True,
            )

        except Exception as exc:
            print(
                f"  WARNING: Could not project "
                f"{game.get('away_team')} @ "
                f"{game.get('home_team')}: {exc}",
                flush=True,
            )

    payload: Dict[str, Any] = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "league": "NBA",
        "season": slate.get("season"),
        "slate_type": slate.get("slate_type"),
        "slate_date": slate.get("slate_date"),
        "game_count": len(games),
        "model_version": "nba-betting-v1",
        "model_status": {
            "game_projections": True,
            "player_baselines": True,
            "live_markets": False,
            "betting_edges": False,
            "best_bets": False,
            "quarters": False,
            "first_basket": False,
        },
        "methodology": {
            "current_season_full_weight_games":
                CURRENT_SEASON_FULL_WEIGHT_GAMES,
            "home_court_advantage":
                HOME_COURT_ADVANTAGE,
            "regression_to_league":
                REGRESSION_TO_LEAGUE,
            "league_baseline_points":
                _round(
                    league.get("points", 0.0),
                    2,
                ),
        },
        "league_baseline": {
            key: _round(value, 2)
            for key, value in league.items()
        },
        "games": games,

        # This becomes populated only after the live-market layer
        # calculates actual model-vs-book edges.
        "best_bets": [],
    }

    _write_json(
        OUTPUT_PATH,
        payload,
    )

    print(
        f"Saved: {OUTPUT_PATH}",
        flush=True,
    )

    try:
        _write_json(
            WEB_OUTPUT_PATH,
            payload,
        )

        print(
            f"Saved web copy: {WEB_OUTPUT_PATH}",
            flush=True,
        )

    except Exception as exc:
        print(
            f"WARNING: Could not write web copy: {exc}",
            flush=True,
        )

    return payload


if __name__ == "__main__":
    build_nba_betting_projections()