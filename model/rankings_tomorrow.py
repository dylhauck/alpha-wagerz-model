import json
from pathlib import Path


ALL_GAMES_FILE = Path("data/tomorrow/all_games.json")
OUTPUT_FILE = Path("data/tomorrow/rankings.json")


def load_json(filepath):
    if not filepath.exists():
        return []

    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data, filepath):
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def get_game_hitters(game, side):
    hitters = game.get("hitters", {})

    if isinstance(hitters, dict):
        return hitters.get(side, [])

    if side == "away":
        return game.get("away_hitters", [])

    if side == "home":
        return game.get("home_hitters", [])

    return []


def build_tomorrow_rankings():
    games = load_json(ALL_GAMES_FILE)

    if not isinstance(games, list):
        raise ValueError(
            f"Expected a list in {ALL_GAMES_FILE}"
        )

    hr_targets = []
    pitchers = []

    for game in games:
        if not isinstance(game, dict):
            continue

        for side in ["away", "home"]:
            for hitter in get_game_hitters(game, side):
                likely = hitter.get("Likely", "")

                if likely != "":
                    hr_targets.append(
                        {
                            "Category": "HR Target",
                            "Player/Team": hitter.get(
                                "Player",
                                "",
                            ),
                            "Game": game.get("game", ""),
                            "Score": likely,
                            "Notes": "",
                        }
                    )

        for pitcher in game.get("pitchers", []):
            score = pitcher.get(
                "Strikeout Score",
                "",
            )

            if score != "":
                pitchers.append(
                    {
                        "Category": "Pitcher K Target",
                        "Player/Team": pitcher.get(
                            "Pitcher",
                            "",
                        ),
                        "Game": game.get("game", ""),
                        "Score": score,
                        "Notes": "",
                    }
                )

    hr_targets.sort(
        key=lambda item: float(item["Score"]),
        reverse=True,
    )

    pitchers.sort(
        key=lambda item: float(item["Score"]),
        reverse=True,
    )

    rankings = {
        "hr_targets": hr_targets[:20],
        "pitchers": pitchers[:20],
    }

    save_json(
        rankings,
        OUTPUT_FILE,
    )

    print(
        f"✅ Built tomorrow rankings "
        f"({len(rankings['hr_targets'])} hitters, "
        f"{len(rankings['pitchers'])} pitchers)"
    )
    print(f"📁 {OUTPUT_FILE}")

    return rankings


if __name__ == "__main__":
    build_tomorrow_rankings()