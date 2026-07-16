from __future__ import annotations

import shutil
from pathlib import Path


MODEL_ROOT = Path(__file__).resolve().parents[1]

WEB_ROOT = MODEL_ROOT.parent / "alpha-wagerz-web"
TOMORROW_DATA_DIR = MODEL_ROOT / "data" / "tomorrow"
WEB_TOMORROW_DATA_DIR = WEB_ROOT / "public" / "data" / "tomorrow"

FILES_TO_PUBLISH = [
    "all_games.json",
    "weather.json",
    "rankings.json",
    "game_projections.json",
    "market_lines.json",
]


def publish_tomorrow_to_web():
    if not WEB_ROOT.exists():
        print(f"⚠️ Web app not found at {WEB_ROOT}")
        return 0

    WEB_TOMORROW_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    published = 0

    for filename in FILES_TO_PUBLISH:
        source = TOMORROW_DATA_DIR / filename
        target = WEB_TOMORROW_DATA_DIR / filename

        if not source.exists():
            print(
                f"⚠️ Missing tomorrow file: {source}"
            )
            continue

        shutil.copy2(
            source,
            target,
        )

        published += 1
        print(
            f"✅ Published tomorrow/{filename}"
        )

    print()
    print(
        f"✅ Published {published} tomorrow files to:"
    )
    print(f"📁 {WEB_TOMORROW_DATA_DIR}")

    return published


if __name__ == "__main__":
    publish_tomorrow_to_web()