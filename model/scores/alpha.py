from model.scores.power import score_power
from model.scores.contact import score_contact
from model.scores.pitcher import score_pitcher
from model.scores.weather import score_weather
from model.scores.park import score_park
from model.scores.recent_form import score_recent_form
from model.scores.confidence import score_confidence, build_score_reasons


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def safe_score(value, default=50):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def score_pitch_type(hitter):
    return safe_score(hitter.get("Pitch Type Score"), 50)


def score_team(hitter):
    return safe_score(hitter.get("Team Offense"), 50)


def score_bullpen(hitter):
    return safe_score(hitter.get("Bullpen"), 50)


def elite_bonus(power, pitcher_score, pitch_type, weather, park, recent):
    bonus = 0

    if power >= 78 and pitcher_score >= 70:
        bonus += 5

    if power >= 85 and pitch_type >= 70:
        bonus += 4

    if pitcher_score >= 78 and pitch_type >= 75:
        bonus += 4

    if weather >= 70:
        bonus += 2

    if park >= 70:
        bonus += 2

    if recent >= 75:
        bonus += 3

    if power >= 88 and pitcher_score >= 80 and pitch_type >= 75:
        bonus += 5

    return bonus


def boost_score(score, midpoint=58, strength=1.28):
    score = safe_score(score, 50)

    if score <= midpoint:
        return score

    return clamp(midpoint + ((score - midpoint) * strength))


def alpha_score(hitter, pitcher=None, game=None):
    power = score_power(hitter)
    contact = score_contact(hitter)
    pitcher_score = score_pitcher(hitter, pitcher)
    pitch_type = score_pitch_type(hitter)
    team = score_team(hitter)
    bullpen = score_bullpen(hitter)
    weather = score_weather(game)
    park = score_park(game, hitter)
    recent = score_recent_form(hitter)

    matchup = (
        pitcher_score * 0.38
        + power * 0.24
        + pitch_type * 0.18
        + contact * 0.10
        + recent * 0.04
        + weather * 0.03
        + park * 0.03
    )

    ceiling = (
        pitcher_score * 0.30
        + power * 0.30
        + pitch_type * 0.16
        + weather * 0.08
        + park * 0.08
        + recent * 0.08
    )

    khr = (
        pitcher_score * 0.36
        + power * 0.30
        + pitch_type * 0.16
        + park * 0.07
        + weather * 0.07
        + recent * 0.04
    )

    zone_fit = (
        pitcher_score * 0.34
        + pitch_type * 0.34
        + power * 0.18
        + contact * 0.14
    )

    matchup = boost_score(matchup, midpoint=55, strength=1.42)
    ceiling = boost_score(ceiling, midpoint=57, strength=1.36)
    khr = boost_score(khr, midpoint=55, strength=1.40)

    bonus = elite_bonus(power, pitcher_score, pitch_type, weather, park, recent)

    likely = (
        matchup * 0.42
        + ceiling * 0.20
        + khr * 0.22
        + team * 0.05
        + bullpen * 0.05
        + recent * 0.04
        + bonus
    )

    likely = clamp(likely)

    scores = {
        "Power": round(power, 1),
        "Contact": round(contact, 1),
        "Pitcher": round(pitcher_score, 1),
        "Pitch Type": round(pitch_type, 1),
        "Team": round(team, 1),
        "Bullpen": round(bullpen, 1),
        "Weather": round(weather, 1),
        "Park": round(park, 1),
        "Recent": round(recent, 1),
        "Matchup": round(matchup, 1),
        "Test Score": round(matchup, 1),
        "Ceiling": round(ceiling, 1),
        "Zone Fit": round(zone_fit, 1),
        "HR Form": round(recent, 1),
        "kHR": round(khr, 1),
        "Likely": round(likely, 1),
    }

    scores["Confidence"] = score_confidence(scores)
    scores["Reasons"] = build_score_reasons(scores)

    return scores