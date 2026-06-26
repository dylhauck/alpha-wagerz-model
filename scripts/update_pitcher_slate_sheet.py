from google_sheets.pitcher_slate_writer import update_pitcher_slate


def main():
    game_id = input("Enter game_id for pitcher slate: ").strip()
    update_pitcher_slate(game_id)


if __name__ == "__main__":
    main()