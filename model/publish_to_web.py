from pathlib import Path
import shutil

MODEL_ROOT = Path(__file__).resolve().parents[1]

WEB_ROOT = MODEL_ROOT.parent / "alpha-wagerz-web"
WEB_DATA_DIR = WEB_ROOT / "public" / "data"

FILES_TO_PUBLISH = [
    "all_games.json",
    "weather.json",
    "rankings.json",
]


def publish_to_web():
    if not WEB_ROOT.exists():
        print(f"⚠️ Web app not found at {WEB_ROOT}")
        return

    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    published = 0

    for filename in FILES_TO_PUBLISH:
        source = MODEL_ROOT / "data" / "processed" / filename
        target = WEB_DATA_DIR / filename

        if not source.exists():
            print(f"⚠️ Missing processed file: {source}")
            continue

        shutil.copy2(source, target)
        published += 1

    print(f"✅ Published {published} files to {WEB_DATA_DIR}")


if __name__ == "__main__":
    publish_to_web()