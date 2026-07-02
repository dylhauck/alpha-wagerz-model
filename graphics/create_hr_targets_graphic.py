from pathlib import Path
from datetime import date
from PIL import Image, ImageDraw, ImageFont
from utils.json_utils import load_json

DATA_FILE = Path("data/processed/hr_targets.json")
OUTPUT_DIR = Path("outputs/graphics")
OUTPUT_FILE = OUTPUT_DIR / "alpha_hr_targets.png"

W, H = 1600, 1000


def font(size, bold=False):
    possible_fonts = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]

    for font_path in possible_fonts:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue

    return ImageFont.load_default()


def short_team(name):
    return {
        "Chicago White Sox": "CWS",
        "Cleveland Guardians": "CLE",
        "Cincinnati Reds": "CIN",
        "Milwaukee Brewers": "MIL",
        "Detroit Tigers": "DET",
        "Texas Rangers": "TEX",
        "Los Angeles Angels": "LAA",
        "Seattle Mariners": "SEA",
        "Miami Marlins": "MIA",
        "Colorado Rockies": "COL",
        "Pittsburgh Pirates": "PIT",
        "Philadelphia Phillies": "PHI",
        "San Diego Padres": "SD",
        "Los Angeles Dodgers": "LAD",
        "St. Louis Cardinals": "STL",
        "Atlanta Braves": "ATL",
        "Tampa Bay Rays": "TB",
        "Kansas City Royals": "KC",
    }.get(name, name[:3].upper())


def draw_text(draw, xy, text, size=28, fill="white", bold=True):
    draw.text(xy, str(text), font=font(size, bold), fill=fill)


def draw_card(draw, x, y, game, idx):
    card_w = 500
    card_h = 150

    draw.rounded_rectangle(
        [x, y, x + card_w, y + card_h],
        radius=18,
        fill=(8, 14, 28),
        outline=(35, 216, 255) if idx % 2 == 0 else (255, 62, 165),
        width=2,
    )

    away = short_team(game["away_team"])
    home = short_team(game["home_team"])

    draw_text(draw, (x + 18, y + 12), f"{idx}. {away} @ {home}", 28, "white")
    draw_text(draw, (x + 18, y + 47), game.get("venue", ""), 17, (70, 220, 255), False)

    players = game.get("away_targets", []) + game.get("home_targets", [])

    y2 = y + 78
    for i, p in enumerate(players[:4], start=1):
        name = p.get("player", "")
        team = short_team(p.get("team", ""))
        likely = p.get("likely", "")

        color = (70, 220, 255) if i in [1, 2] else (255, 62, 165)
        draw_text(draw, (x + 18, y2), "★", 22, color)
        draw_text(draw, (x + 48, y2), f"{name} ({team})", 21, "white")
        draw_text(draw, (x + card_w - 92, y2), f"{likely}", 20, color)
        y2 += 28


def create_graphic():
    games = load_json(DATA_FILE, default=[])
    games = sorted(games, key=lambda g: g.get("game_time", ""))

    img = Image.new("RGB", (W, H), (3, 7, 18))
    draw = ImageDraw.Draw(img)

    # background glow
    draw.ellipse([-350, -250, 550, 650], fill=(0, 50, 80))
    draw.ellipse([1050, -250, 1850, 650], fill=(90, 0, 55))

    draw_text(draw, (70, 35), "ALPHA", 58, "white")
    draw_text(draw, (300, 35), "HOME RUN TARGETS", 58, (70, 220, 255))
    draw_text(draw, (70, 105), "TOP 2 HR TARGETS FROM EACH TEAM", 30, (255, 255, 255))

    today = f"{date.today():%A, %B} {date.today().day}".upper()
    draw_text(draw, (70, 150), today, 24, (255, 62, 165))

    positions = [
        (60, 210), (550, 210), (1040, 210),
        (60, 390), (550, 390), (1040, 390),
        (60, 570), (550, 570), (1040, 570),
    ]

    for idx, game in enumerate(games[:9], start=1):
        draw_card(draw, positions[idx - 1][0], positions[idx - 1][1], game, idx)

    draw_text(draw, (470, 910), "FOLLOW THE ALPHA", 42, (255, 62, 165))
    draw_text(draw, (660, 955), "WEATHER. MATCHUP. DATA. EDGE.", 22, (70, 220, 255))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT_FILE)

    print(f"✅ Saved HR graphic: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_graphic()