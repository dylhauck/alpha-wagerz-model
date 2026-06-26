from google_sheets.update_selected_game import update_selected_game_sheets


def main():
    game_id = input("Enter game_id: ").strip()
    update_selected_game_sheets(game_id)


if __name__ == "__main__":
    main()