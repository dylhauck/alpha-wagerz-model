from google_sheets.dashboard_writer import update_selected_game_dashboard


def main():
    game_id = input("Enter game_id to update Google Sheet: ").strip()
    update_selected_game_dashboard(game_id)


if __name__ == "__main__":
    main()