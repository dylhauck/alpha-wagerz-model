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

    score = 50 + ((hr_factor - 100) * 1.5)

    return round(clamp(score), 1)