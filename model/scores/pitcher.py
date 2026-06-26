def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def f(value):
    try:
        if value == "" or value is None:
            return 0.0
        return float(value)
    except:
        return 0.0


def score_pitcher(hitter, pitcher):
    if not pitcher:
        return 50

    xwoba = f(pitcher.get("xwOBA"))
    brl = f(pitcher.get("Brl/BIP%"))
    hh = f(pitcher.get("HH%"))
    fb = f(pitcher.get("FB%"))
    swstr = f(pitcher.get("SwStr%"))
    ball = f(pitcher.get("Ball%"))

    vulnerability = (
        xwoba * 90 +
        brl * 1.7 +
        hh * 0.7 +
        fb * 0.45 +
        ball * 0.25 -
        swstr * 0.65
    )

    return round(clamp(vulnerability), 1)