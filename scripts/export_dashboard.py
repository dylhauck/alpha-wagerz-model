from model.dashboard import build_dashboard_payload
from utils.file_utils import save_json


def main():
    game_id = input("Enter game_id to export: ").strip()

    payload = build_dashboard_payload(game_id)

    save_json(payload, "outputs/dashboard_selected_game.json")

    print("✅ Exported selected game dashboard")
    print("📁 outputs/dashboard_selected_game.json")


if __name__ == "__main__":
    main()