import json
import math
from pathlib import Path

import pandas as pd


def clean_value(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    try:
        if isinstance(value, (int, float)) and not math.isfinite(value):
            return ""
    except Exception:
        pass

    try:
        if str(value).lower() in ["nan", "inf", "infinity", "-inf", "-infinity"]:
            return ""
    except Exception:
        pass

    return value


def clean_json(obj):
    if isinstance(obj, dict):
        return {key: clean_json(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [clean_json(value) for value in obj]

    return clean_value(obj)


def load_json(filepath, default=None):
    filepath = Path(filepath)

    if not filepath.exists():
        return default

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    cleaned = clean_json(data)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, allow_nan=False)