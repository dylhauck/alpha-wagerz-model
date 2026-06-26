from model.load_weights import load_weights

from model.scores.power import score_power
from model.scores.contact import score_contact
from model.scores.pitcher import score_pitcher
from model.scores.weather import score_weather
from model.scores.park import score_park
from model.scores.recent_form import score_recent_form


def alpha_score(hitter, pitcher=None, game=None):
    weights = load_weights()

    power = score_power(hitter)
    contact = score_contact(hitter)
    pitcher_score = score_pitcher(hitter, pitcher)
    weather = score_weather(game)
    park = score_park(game, hitter)
    recent = score_recent_form(hitter)

    score = (
        power * weights["power"]
        + contact * weights["contact"]
        + pitcher_score * weights["pitcher"]
        + weather * weights["weather"]
        + park * weights["park"]
        + recent * weights["recent"]
    )

    return {
        "Power": round(power, 1),
        "Contact": round(contact, 1),
        "Pitcher": round(pitcher_score, 1),
        "Weather": round(weather, 1),
        "Park": round(park, 1),
        "Recent": round(recent, 1),
        "Likely": round(score, 1),
    }