from google_sheets.hitters_writer import update_hitter_matchups


def main():
    game_id = input("Enter game_id for hitter matchups: ").strip()
    update_hitter_matchups(game_id)


if __name__ == "__main__":
    main()