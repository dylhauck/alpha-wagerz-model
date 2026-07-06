from pathlib import Path
import pandas as pd

PARK_FACTORS_FILE = Path("data/reference/park_factors.csv")


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def load_park_factors():
    if not PARK_FACTORS_FILE.exists():
        return {}

    df = pd.read_csv(PARK_FACTORS_FILE)

    return {
        row["Stadium"]: row.to_dict()
        for _, row in df.iterrows()
    }


def score_park(game=None, hitter=None):
    if not game:
        return 50

    venue = game.get("venue", "")
    park_lookup = load_park_factors()
    park = park_lookup.get(venue)

    if not park:
        return 50

    hr_factor = float(park.get("HR Factor", 100))

    # Wider spread than before.
    # 80 HR factor ≈ 20
    # 100 HR factor = 50
    # 120 HR factor ≈ 80
    score = 50 + ((hr_factor - 100) * 1.5)

    # Manual boost/suppression for parks that play extreme
    extreme_adjustments = {
        "Coors Field": 10,
        "Great American Ball Park": 8,
        "Yankee Stadium": 5,
        "Citizens Bank Park": 5,
        "Wrigley Field": 4,
        "T-Mobile Park": -6,
        "Oracle Park": -7,
        "Comerica Park": -4,
        "Kauffman Stadium": -4,
    }

    score += extreme_adjustments.get(venue, 0)

    return round(clamp(score), 1)