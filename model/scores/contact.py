def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def f(value):
    try:
        return float(value)
    except:
        return 0.0


def score_contact(hitter):
    xwoba = f(hitter.get("xwOBA"))
    sweet = f(hitter.get("Sweet Spot%"))
    swstr = f(hitter.get("SwStr%"))

    score = (
        xwoba * 120 +
        sweet * 0.65 -
        swstr * 0.45
    )

    return round(clamp(score), 1)