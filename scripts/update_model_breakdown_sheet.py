from google_sheets.model_breakdown_writer import update_model_breakdown


def main():
    game_id = input("Enter game_id: ").strip()
    update_model_breakdown(game_id)


if __name__ == "__main__":
    main()