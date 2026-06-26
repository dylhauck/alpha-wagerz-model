def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def score_confidence(scores):
    power = scores.get("Power", 0)
    pitcher = scores.get("Pitcher", 0)
    weather = scores.get("Weather", 0)
    park = scores.get("Park", 0)
    recent = scores.get("Recent", 0)

    confidence = 50

    if power >= 75:
        confidence += 12
    elif power >= 60:
        confidence += 6

    if pitcher >= 70:
        confidence += 10
    elif pitcher >= 60:
        confidence += 5

    if weather >= 65:
        confidence += 8
    elif weather <= 40:
        confidence -= 8

    if park >= 60:
        confidence += 6
    elif park <= 40:
        confidence -= 6

    if recent >= 65:
        confidence += 5

    return round(clamp(confidence), 1)


def build_score_reasons(scores):
    reasons = []

    if scores.get("Power", 0) >= 75:
        reasons.append("Elite power profile")
    elif scores.get("Power", 0) >= 60:
        reasons.append("Strong power profile")

    if scores.get("Pitcher", 0) >= 70:
        reasons.append("Favorable pitcher vulnerability")
    elif scores.get("Pitcher", 0) >= 60:
        reasons.append("Positive pitcher matchup")

    if scores.get("Weather", 0) >= 65:
        reasons.append("Weather boosts carry")
    elif scores.get("Weather", 0) <= 40:
        reasons.append("Weather suppresses HR upside")

    if scores.get("Park", 0) >= 60:
        reasons.append("Park boosts HR potential")
    elif scores.get("Park", 0) <= 40:
        reasons.append("Park suppresses HR potential")

    if scores.get("Recent", 0) >= 65:
        reasons.append("Recent form is positive")

    if not reasons:
        reasons.append("Balanced profile with no major edge")

    return reasons