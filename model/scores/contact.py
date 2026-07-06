def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def f(value):
    try:
        if value == "" or value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def scale(value, bad, elite):
    if elite == bad:
        return 50
    return clamp((value - bad) / (elite - bad) * 100)


def inverse_scale(value, elite, bad):
    if bad == elite:
        return 50
    return clamp((bad - value) / (bad - elite) * 100)


def score_contact(hitter):
    xwoba = f(hitter.get("xwOBA"))
    sweet = f(hitter.get("Sweet Spot%"))
    swstr = f(hitter.get("SwStr%"))

    score = (
        scale(xwoba, 0.250, 0.420) * 0.45 +
        scale(sweet, 24.0, 42.0) * 0.30 +
        inverse_scale(swstr, 6.0, 18.0) * 0.25
    )

    return round(clamp(score), 1)