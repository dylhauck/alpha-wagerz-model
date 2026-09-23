import json
from pathlib import Path

WEIGHTS_FILE = Path("data/reference/mlb/scoring_weights.json")


def load_weights():
    with open(WEIGHTS_FILE, "r") as f:
        return json.load(f)

