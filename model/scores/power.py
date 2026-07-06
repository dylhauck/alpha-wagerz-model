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


def score_power(hitter):
    iso = f(hitter.get("ISO"))
    hh = f(hitter.get("HH%"))
    brl = f(hitter.get("Brl/BIP%"))
    pulled = f(hitter.get("PulledBrl%"))
    xwobacon = f(hitter.get("xwOBAcon"))

    score = (
        scale(iso, 0.080, 0.280) * 0.25 +
        scale(xwobacon, 0.280, 0.520) * 0.25 +
        scale(brl, 4.0, 18.0) * 0.22 +
        scale(hh, 32.0, 60.0) * 0.18 +
        scale(pulled, 2.0, 12.0) * 0.10
    )

    return round(clamp(score), 1)