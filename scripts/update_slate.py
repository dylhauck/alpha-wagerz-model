from providers.mlb import get_todays_slate
from utils.file_utils import save_json
import pandas as pd


def main():
    slate = get_todays_slate()

    save_json(slate, "data/raw/todays_slate.json")

    df = pd.DataFrame(slate)
    df.to_csv("data/processed/slate_summary.csv", index=False)

    print(f"✅ Saved {len(df)} games")
    print("📁 data/raw/todays_slate.json")
    print("📁 data/processed/slate_summary.csv")


if __name__ == "__main__":
    main()