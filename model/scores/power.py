def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def f(value):
    try:
        return float(value)
    except:
        return 0.0


def score_power(hitter):
    iso = f(hitter.get("ISO"))
    hh = f(hitter.get("HH%"))
    brl = f(hitter.get("Brl/BIP%"))
    pulled = f(hitter.get("PulledBrl%"))
    xwobacon = f(hitter.get("xwOBAcon"))

    score = (
        iso * 140 +
        hh * 0.55 +
        brl * 1.25 +
        pulled * 0.90 +
        xwobacon * 70
    )

    return round(clamp(score), 1)