from pathlib import Path
from datetime import date
from PIL import Image, ImageDraw, ImageFont
from utils.json_utils import load_json

DATA_FILE = Path("data/processed/weather.json")
OUTPUT_DIR = Path("outputs/graphics")
OUTPUT_FILE = OUTPUT_DIR / "alpha_weather_edge.png"

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


def draw_text(draw, xy, text, size=28, fill="white", bold=True):
    draw.text(xy, str(text), font=font(size, bold), fill=fill)


def short_game(game):
    teams = game.get("game", "")
    return (
        teams.replace("Chicago White Sox", "CWS")
        .replace("Cleveland Guardians", "CLE")
        .replace("Cincinnati Reds", "CIN")
        .replace("Milwaukee Brewers", "MIL")
        .replace("Detroit Tigers", "DET")
        .replace("Texas Rangers", "TEX")
        .replace("Los Angeles Angels", "LAA")
        .replace("Seattle Mariners", "SEA")
        .replace("Miami Marlins", "MIA")
        .replace("Colorado Rockies", "COL")
        .replace("Pittsburgh Pirates", "PIT")
        .replace("Philadelphia Phillies", "PHI")
        .replace("San Diego Padres", "SD")
        .replace("Los Angeles Dodgers", "LAD")
        .replace("St. Louis Cardinals", "STL")
        .replace("Atlanta Braves", "ATL")
        .replace("Tampa Bay Rays", "TB")
        .replace("Kansas City Royals", "KC")
    )


def impact(game):
    wind = str(game.get("wind_direction", "")).upper()
    speed = float(game.get("wind_speed") or 0)
    temp = float(game.get("temperature") or 0)
    venue = game.get("venue", "")

    if "IN" in wind:
        return "SUPPRESSION", (35, 216, 255)

    if "NEUTRAL" in wind:
        if venue == "Coors Field":
            return "NEUTRAL / COORS", (255, 208, 40)
        return "NEUTRAL", (255, 208, 40)

    if "OUT" in wind and (speed >= 8 or temp >= 85):
        return "ELITE", (255, 62, 165)

    if "OUT" in wind:
        return "POSITIVE", (70, 220, 255)

    return "NEUTRAL", (255, 208, 40)


def arrow_for(game):
    wind = str(game.get("wind_direction", "")).upper()

    if "IN" in wind:
        return "↓"

    if "NEUTRAL" in wind:
        return "↔"

    if "OUT" in wind:
        return "↗"

    return "↔"


def draw_weather_card(draw, x, y, game, idx):
    label, color = impact(game)

    draw.rounded_rectangle(
        [x, y, x + 470, y + 145],
        radius=18,
        fill=(8, 14, 28),
        outline=color,
        width=2,
    )

    draw_text(draw, (x + 18, y + 12), f"{idx}. {short_game(game)}", 28, "white")
    draw_text(draw, (x + 18, y + 48), game.get("venue", ""), 18, (70, 220, 255), False)

    temp = round(float(game.get("temperature") or 0))
    condition = game.get("conditions", "—")
    wind = game.get("wind_direction", "—")
    speed = round(float(game.get("wind_speed") or 0))

    draw_text(draw, (x + 18, y + 80), f"{temp}°F | {condition}", 22, "white")
    draw_text(draw, (x + 18, y + 110), f"WIND: {wind} {speed} MPH", 20, color)

    draw_text(draw, (x + 390, y + 42), arrow_for(game), 62, color)
    draw_text(draw, (x + 330, y + 108), label, 20, color)


def create_weather_graphic():
    games = load_json(DATA_FILE, default=[])

    img = Image.new("RGB", (W, H), (3, 7, 18))
    draw = ImageDraw.Draw(img)

    draw.ellipse([-350, -250, 550, 650], fill=(0, 50, 80))
    draw.ellipse([1050, -250, 1850, 650], fill=(90, 0, 55))

    draw_text(draw, (70, 35), "ALPHA", 58, "white")
    draw_text(draw, (300, 35), "WEATHER EDGE REPORT", 58, (70, 220, 255))
    draw_text(draw, (70, 105), "WEATHER IMPACTING HOME RUNS", 30, (255, 255, 255))

    today = f"{date.today():%A, %B} {date.today().day}".upper()
    draw_text(draw, (70, 150), today, 24, (255, 62, 165))

    elite = []
    positive = []
    neutral = []
    suppression = []

    for game in games:
        label, _ = impact(game)

        if label == "ELITE":
            elite.append(game)
        elif label == "POSITIVE":
            positive.append(game)
        elif label == "SUPPRESSION":
            suppression.append(game)
        else:
            neutral.append(game)

    sections = [
        ("ELITE HR ENVIRONMENTS", elite, 60, 220),
        ("POSITIVE HR ENVIRONMENTS", positive, 560, 220),
        ("NEUTRAL ENVIRONMENTS", neutral, 1060, 220),
        ("HR SUPPRESSION SPOTS", suppression, 1060, 580),
    ]

    for title, items, x, y in sections:
        draw_text(draw, (x, y - 42), title, 28, (255, 62, 165) if "ELITE" in title else (70, 220, 255))
        for i, game in enumerate(items[:3], start=1):
            draw_weather_card(draw, x, y + (i - 1) * 165, game, i)

    boosts = sorted(
        games,
        key=lambda g: (
            1 if "OUT" in str(g.get("wind_direction", "")).upper() else 0,
            float(g.get("temperature") or 0),
            float(g.get("wind_speed") or 0),
        ),
        reverse=True,
    )[:5]

    draw.rounded_rectangle(
        [60, 750, 1040, 900],
        radius=18,
        fill=(8, 14, 28),
        outline=(35, 216, 255),
        width=2,
    )

    draw_text(draw, (390, 765), "TOP WEATHER BOOSTS", 30, "white")

    x = 90
    for i, game in enumerate(boosts, start=1):
        label, color = impact(game)
        draw_text(draw, (x, 810), f"{i}. {short_game(game)}", 22, "white")
        draw_text(draw, (x, 842), game.get("venue", ""), 15, (70, 220, 255), False)
        draw_text(draw, (x, 868), f"{arrow_for(game)} {round(float(game.get('wind_speed') or 0))} MPH", 22, color)
        x += 185

    draw.rounded_rectangle(
        [1080, 750, 1530, 900],
        radius=18,
        fill=(8, 14, 28),
        outline=(255, 62, 165),
        width=2,
    )

    draw_text(draw, (1110, 770), "ALPHA TAKEAWAYS", 30, (255, 62, 165))
    draw_text(draw, (1110, 815), "↗ WIND OUT = MORE HR BOOST", 20, "white")
    draw_text(draw, (1110, 845), "↓ WIND IN = HR SUPPRESSION", 20, "white")
    draw_text(draw, (1110, 875), "↔ NEUTRAL = MODERATE IMPACT", 20, "white")

    draw_text(draw, (520, 940), "FOLLOW THE ALPHA", 42, (255, 62, 165))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT_FILE)

    print(f"✅ Saved weather graphic: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_weather_graphic()