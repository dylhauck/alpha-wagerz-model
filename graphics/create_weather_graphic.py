import math
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.json_utils import load_json

WEATHER_FILE = ROOT / "data/processed/weather.json"
OUTPUT_DIR = ROOT / "graphics/weather"
OUTPUT_FILE = OUTPUT_DIR / f"alpha_weather_edge_{datetime.now().strftime('%Y_%m_%d')}.png"

LOGO_PATHS = [
    ROOT / "assets/alpha-wagerz-logo.png",
    ROOT / "assets/alpha-wagerz-transparent.png",
    ROOT / "public/alpha-wagerz-logo.png",
    ROOT / "public/alpha-wagerz-transparent.png",
]

WOLF_PATHS = [
    ROOT / "assets/wolf.png",
    ROOT / "assets/alpha-wolf.png",
    ROOT / "public/wolf.png",
    ROOT / "public/alpha-wolf.png",
]

WIDTH = 1600
HEIGHT = 2000

BG = (7, 10, 28)
PANEL = (13, 20, 45)
PANEL_2 = (18, 27, 58)
CYAN = (35, 216, 255)
PURPLE = (168, 85, 247)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
WHITE = (245, 247, 255)
MUTED = (148, 163, 184)


def font(size, bold=False):
    paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


FONT_TITLE = font(86, True)
FONT_BIG = font(54, True)
FONT_SECTION = font(38, True)
FONT_CARD = font(28, True)
FONT_SMALL = font(23, True)
FONT_TINY = font(19, True)
FONT_BODY = font(22, False)


def find_existing(paths):
    for path in paths:
        if path.exists():
            return path
    return None


def rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def paste_contain(base, path, box, opacity=1.0):
    if not path or not Path(path).exists():
        return

    img = Image.open(path).convert("RGBA")

    if opacity < 1:
        alpha = img.getchannel("A")
        alpha = alpha.point(lambda p: int(p * opacity))
        img.putalpha(alpha)

    x1, y1, x2, y2 = box
    max_w = x2 - x1
    max_h = y2 - y1

    img.thumbnail((max_w, max_h), Image.LANCZOS)

    x = x1 + (max_w - img.width) // 2
    y = y1 + (max_h - img.height) // 2

    base.alpha_composite(img, (x, y))


def text_center(draw, xy, text, fill, font_obj):
    draw.text(xy, text, fill=fill, font=font_obj, anchor="mm")


def text_size(draw, text, font_obj):
    box = draw.textbbox((0, 0), str(text), font=font_obj)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw, text, font_obj, max_width):
    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()
        if text_size(draw, test, font_obj)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def short_game_name(game):
    aliases = {
        "Arizona Diamondbacks": "ARI", "San Diego Padres": "SD",
        "Athletics": "ATH", "Oakland Athletics": "OAK", "Detroit Tigers": "DET",
        "Atlanta Braves": "ATL", "Pittsburgh Pirates": "PIT",
        "Boston Red Sox": "BOS", "Chicago White Sox": "CWS",
        "Chicago Cubs": "CHC", "Baltimore Orioles": "BAL",
        "Cleveland Guardians": "CLE", "Minnesota Twins": "MIN",
        "Colorado Rockies": "COL", "Los Angeles Dodgers": "LAD",
        "Houston Astros": "HOU", "Washington Nationals": "WAS",
        "Kansas City Royals": "KC", "New York Mets": "NYM",
        "Los Angeles Angels": "LAA", "Texas Rangers": "TEX",
        "Milwaukee Brewers": "MIL", "St. Louis Cardinals": "STL",
        "New York Yankees": "NYY", "Tampa Bay Rays": "TB",
        "Philadelphia Phillies": "PHI", "Cincinnati Reds": "CIN",
        "Seattle Mariners": "SEA", "Miami Marlins": "MIA",
        "Toronto Blue Jays": "TOR", "San Francisco Giants": "SF",
    }

    if " @ " not in str(game):
        return str(game)

    away, home = game.split(" @ ", 1)
    return f"{aliases.get(away, away)} @ {aliases.get(home, home)}"


def classify_weather(row):
    roof = str(row.get("roof", "")).lower()
    wind = str(row.get("wind_direction", "")).upper()
    speed = float(row.get("wind_speed") or 0)
    temp = float(row.get("temperature") or 0)

    if roof in {"dome", "closed"}:
        return "Neutral"

    if "IN" in wind and speed >= 5:
        return "Suppression"

    if "OUT" in wind or temp >= 86:
        return "Positive"

    return "Neutral"


def category_color(category):
    if category == "Positive":
        return GREEN
    if category == "Suppression":
        return RED
    return CYAN


def arrow_angle(row):
    wind = str(row.get("wind_direction", "")).upper()

    if "OUT TOWARDS RF" in wind:
        return -35
    if "OUT TOWARDS LF" in wind:
        return 35
    if "OUT" in wind:
        return 0
    if "IN" in wind:
        return 180
    return 90


def wind_label(row):
    wind = str(row.get("wind_direction", "")).upper()

    if "OUT TOWARDS RF" in wind:
        return "Out to RF"
    if "OUT TOWARDS LF" in wind:
        return "Out to LF"
    if "OUT" in wind:
        return "Out"
    if "IN" in wind:
        return "In"
    return "Neutral"


def draw_arrow(draw, cx, cy, angle_deg, color):
    length = 42
    rad = math.radians(angle_deg - 90)
    x2 = cx + math.cos(rad) * length
    y2 = cy + math.sin(rad) * length

    draw.line((cx, cy, x2, y2), fill=color, width=7)

    head = 15
    left = math.radians(angle_deg - 90 + 145)
    right = math.radians(angle_deg - 90 - 145)

    p1 = (x2, y2)
    p2 = (x2 + math.cos(left) * head, y2 + math.sin(left) * head)
    p3 = (x2 + math.cos(right) * head, y2 + math.sin(right) * head)

    draw.polygon([p1, p2, p3], fill=color)


def draw_card(draw, row, x, y, w, h):
    category = classify_weather(row)
    color = category_color(category)

    rounded_rect(draw, (x, y, x + w, y + h), 24, PANEL_2, outline=color, width=3)

    game = short_game_name(row.get("game", ""))
    venue = row.get("venue", "")
    temp = row.get("temperature", "—")
    speed = row.get("wind_speed", "—")
    conditions = row.get("conditions", "—")

    draw.text((x + 22, y + 16), game, font=FONT_CARD, fill=WHITE)
    draw.text((x + 22, y + 50), str(venue)[:30], font=FONT_TINY, fill=MUTED)

    draw.text((x + 22, y + 87), f"{temp}°", font=FONT_BIG, fill=WHITE)
    draw.text((x + 118, y + 98), str(conditions)[:24], font=FONT_TINY, fill=MUTED)

    draw_arrow(draw, x + w - 48, y + 61, arrow_angle(row), color)

    draw.text((x + 22, y + h - 43), f"Wind: {wind_label(row)}", font=FONT_SMALL, fill=color)
    draw.text((x + w - 132, y + h - 43), f"{speed} MPH", font=FONT_SMALL, fill=WHITE)


def draw_section(draw, title, rows, x, y, w, h, color):
    rounded_rect(draw, (x, y, x + w, y + h), 34, (10, 15, 35), outline=color, width=4)

    draw.text((x + 30, y + 24), title, font=FONT_SECTION, fill=color)

    if not rows:
        draw.text((x + 30, y + 95), "No games", font=FONT_BODY, fill=MUTED)
        return

    card_h = 145
    gap = 18
    start_y = y + 86
    max_cards = max(1, int((h - 110) / (card_h + gap)))

    if len(rows) > max_cards:
        card_h = max(105, int((h - 110 - gap * (len(rows) - 1)) / len(rows)))

    for i, row in enumerate(rows):
        cy = start_y + i * (card_h + gap)
        if cy + card_h > y + h - 20:
            break
        draw_card(draw, row, x + 22, cy, w - 44, card_h)


def alpha_takeaways(rows):
    positives = [r for r in rows if classify_weather(r) == "Positive"]
    suppress = [r for r in rows if classify_weather(r) == "Suppression"]

    boosts = sorted(
        positives,
        key=lambda r: (float(r.get("wind_speed") or 0), float(r.get("temperature") or 0)),
        reverse=True,
    )[:3]

    notes = []

    if boosts:
        notes.append(
            "Best HR weather boosts: "
            + ", ".join(short_game_name(r.get("game", "")) for r in boosts)
            + "."
        )

    if suppress:
        notes.append(
            "Suppression spots: "
            + ", ".join(short_game_name(r.get("game", "")) for r in suppress[:3])
            + "."
        )

    if not notes:
        notes.append("Slate is mostly neutral from a weather perspective.")

    return notes


def draw_takeaways(draw, rows):
    x, y, w, h = 90, 1678, 1420, 185
    rounded_rect(draw, (x, y, x + w, y + h), 30, PANEL, outline=PURPLE, width=4)

    draw.text((x + 34, y + 24), "ALPHA TAKEAWAYS", font=FONT_SECTION, fill=PURPLE)

    ty = y + 82

    for note in alpha_takeaways(rows)[:3]:
        for line in wrap_text(draw, f"• {note}", FONT_BODY, w - 70):
            draw.text((x + 34, ty), line, font=FONT_BODY, fill=WHITE)
            ty += 30
        ty += 6


def create_weather_graphic():
    rows = load_json(WEATHER_FILE, default=[])

    if not rows:
        print(f"⏭️ No weather rows found at {WEATHER_FILE}. Skipping weather graphic.")
        return None
    
    rows = sorted(
        rows,
        key=lambda r: (
            {"Positive": 0, "Neutral": 1, "Suppression": 2}.get(classify_weather(r), 3),
            str(r.get("game", "")),
        ),
    )

    positive = [r for r in rows if classify_weather(r) == "Positive"]
    neutral = [r for r in rows if classify_weather(r) == "Neutral"]
    suppression = [r for r in rows if classify_weather(r) == "Suppression"]

    img = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    draw = ImageDraw.Draw(img)

    for i in range(0, 900, 18):
        color = (35, 216, 255, max(0, 55 - i // 18))
        draw.ellipse((WIDTH - 700 - i, -260 - i, WIDTH + 250 + i, 670 + i), outline=color, width=2)

    logo = find_existing(LOGO_PATHS)
    wolf = find_existing(WOLF_PATHS)

    if logo:
        paste_contain(img, logo, (72, 48, 310, 170))
    else:
        draw.text((85, 68), "ALPHA", font=FONT_BIG, fill=WHITE)
        draw.text((85, 121), "WAGERZ", font=FONT_SMALL, fill=CYAN)

    today = datetime.now()
    date_line = today.strftime("%A, %B %-d, %Y") if sys.platform != "win32" else today.strftime("%A, %B %#d, %Y")

    text_center(draw, (WIDTH // 2, 75), "ALPHA WEATHER EDGE", WHITE, FONT_TITLE)
    text_center(draw, (WIDTH // 2, 150), date_line.upper(), CYAN, FONT_SECTION)

    draw.text((1090, 72), "MLB SLATE", font=FONT_SECTION, fill=WHITE)
    draw.text((1090, 118), f"{len(rows)} GAMES LOADED", font=FONT_SMALL, fill=MUTED)

    left_x = 70
    top_y = 230
    col_w = 470
    section_h = 1405
    gap = 25

    draw_section(draw, "POSITIVE ENVIRONMENTS", positive, left_x, top_y, col_w, section_h, GREEN)
    draw_section(draw, "NEUTRAL ENVIRONMENTS", neutral, left_x + col_w + gap, top_y, col_w, section_h, CYAN)
    draw_section(draw, "SUPPRESSION ENVIRONMENTS", suppression, left_x + (col_w + gap) * 2, top_y, col_w, section_h, RED)

    draw_takeaways(draw, rows)

    if wolf:
        paste_contain(img, wolf, (650, 1760, 950, 1990), opacity=0.92)

    draw.text((70, 1930), "Alpha Wagerz • Weather model updates automatically from game-time forecast", font=FONT_SMALL, fill=MUTED)
    draw.text((1230, 1930), "Not betting advice", font=FONT_SMALL, fill=MUTED)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUTPUT_FILE, quality=95)

    print("✅ Saved weather graphic")
    print(f"📁 {OUTPUT_FILE}")

    return OUTPUT_FILE


if __name__ == "__main__":
    create_weather_graphic()
