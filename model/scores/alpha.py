from model.load_weights import load_weights

from model.scores.power import score_power
from model.scores.contact import score_contact
from model.scores.pitcher import score_pitcher
from model.scores.weather import score_weather
from model.scores.park import score_park
from model.scores.recent_form import score_recent_form
from model.scores.confidence import score_confidence, build_score_reasons


def score_pitch_type(hitter):
    try:
        value = hitter.get("Pitch Type Score", 50)
        if value == "" or value is None:
            return 50
        return float(value)
    except Exception:
        return 50
    
def score_team(hitter):
    try:
        value = hitter.get("Team Offense", 50)
        if value == "" or value is None:
            return 50
        return float(value)
    except Exception:
        return 50


def alpha_score(hitter, pitcher=None, game=None):
    weights = load_weights()

    power = score_power(hitter)
    contact = score_contact(hitter)
    pitcher_score = score_pitcher(hitter, pitcher)
    pitch_type = score_pitch_type(hitter)
    weather = score_weather(game)
    park = score_park(game, hitter)
    recent = score_recent_form(hitter)
    team = score_team(hitter)

    likely = (
        power * weights["power"]
        + contact * weights["contact"]
        + pitcher_score * weights["pitcher"]
        + pitch_type * weights["pitch_type"]
        + weather * weights["weather"]
        + park * weights["park"]
        + recent * weights["recent"]
        + team * weights["team"]
    )

    scores = {
        "Power": round(power, 1),
        "Contact": round(contact, 1),
        "Pitcher": round(pitcher_score, 1),
        "Pitch Type": round(pitch_type, 1),
        "Team": round(team, 1),
        "Weather": round(weather, 1),
        "Park": round(park, 1),
        "Recent": round(recent, 1),
        "Likely": round(likely, 1),
    }

    scores["Confidence"] = score_confidence(scores)
    scores["Reasons"] = build_score_reasons(scores)

    return scores