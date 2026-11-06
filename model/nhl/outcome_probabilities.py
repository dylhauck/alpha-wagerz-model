"""NHL baseline outcome probabilities from independent Poisson team goal counts.

This is an uncalibrated historical scoring model, NOT a validated betting model.
A regulation tie is split 50/50 as a neutral overtime/shootout assumption.
Do not infer probabilities from sportsbook payouts.
"""
from __future__ import annotations
import math


def poisson_pmf(mean: float, limit: int = 24) -> list[float]:
    if not math.isfinite(mean) or mean <= 0:
        raise ValueError("Expected goals must be finite and positive")
    values = [math.exp(-mean)]
    for k in range(1, limit + 1):
        values.append(values[-1] * mean / k)
    # Normalize tiny truncated tail for a well-defined distribution.
    total = sum(values)
    return [value / total for value in values]


def outcome_probabilities(away_goals: float | None, home_goals: float | None,
                          sample_games: int, minimum_games: int = 5) -> dict | None:
    if away_goals is None or home_goals is None or sample_games < minimum_games:
        return None
    if not all(math.isfinite(x) and x > 0 for x in (away_goals, home_goals)):
        return None
    a, h = poisson_pmf(away_goals), poisson_pmf(home_goals)
    away_reg = home_reg = tie = home_puck_cover = away_puck_cover = 0.0
    for ai, ap in enumerate(a):
        for hi, hp in enumerate(h):
            p = ap * hp
            if ai > hi:
                away_reg += p
            elif hi > ai:
                home_reg += p
            else:
                tie += p
            if hi - ai >= 2:
                home_puck_cover += p
            if ai - hi >= -1:
                away_puck_cover += p
    # Moneyline includes OT/shootout. A tied regulation game is assumed
    # equally likely to be won by either side until OT-specific data exists.
    return {
        "away_win_probability": round(away_reg + tie / 2, 5),
        "home_win_probability": round(home_reg + tie / 2, 5),
        "away_puck_line_plus_1_5_probability": round(away_puck_cover, 5),
        "home_puck_line_minus_1_5_probability": round(home_puck_cover, 5),
        "method": "independent_poisson_goals_regulation_tie_split_equally",
        "calibrated": False,
        "sample_games": sample_games,
        "limitations": "Baseline only: no verified starting goalies, injuries, OT team strengths or probability calibration.",
    }
