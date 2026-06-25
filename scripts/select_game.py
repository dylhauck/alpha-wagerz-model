from model.game_selector import list_games, get_game_by_id


def main():
    print("\nAvailable Games:")
    list_games()

    game_id = input("\nEnter game_id: ").strip()

    game = get_game_by_id(game_id)

    print("\n==============================")
    print(f"Selected Game: {game['game']}")
    print("==============================")
    print(f"Venue: {game['venue']}")
    print(f"Away SP: {game['away_sp']}")
    print(f"Home SP: {game['home_sp']}")
    print(f"Status: {game['status']}")


if __name__ == "__main__":
    main()