def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def safe_float(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def score_hitter_likely(hitter):
    iso = safe_float(hitter.get("ISO"))
    xwoba = safe_float(hitter.get("xwOBA"))
    xwobacon = safe_float(hitter.get("xwOBAcon"))
    swstr = safe_float(hitter.get("SwStr%"))
    pulled_brl = safe_float(hitter.get("PulledBrl%"))
    brl_bip = safe_float(hitter.get("Brl/BIP%"))
    sweet_spot = safe_float(hitter.get("Sweet Spot%"))
    fb = safe_float(hitter.get("FB%"))
    hh = safe_float(hitter.get("HH%"))
    la = safe_float(hitter.get("LA"))
    pitches = safe_float(hitter.get("Pitches"))
    bip = safe_float(hitter.get("BIP"))

    power_score = (
        iso * 120 +
        xwobacon * 80 +
        brl_bip * 1.4 +
        pulled_brl * 1.1 +
        hh * 0.6
    )

    contact_shape_score = (
        sweet_spot * 0.45 +
        fb * 0.35
    )

    launch_angle_score = 0
    if 15 <= la <= 28:
        launch_angle_score = 12
    elif 10 <= la < 15 or 28 < la <= 35:
        launch_angle_score = 7
    else:
        launch_angle_score = 2

    discipline_penalty = swstr * 0.35

    sample_score = 0
    if pitches >= 1000 and bip >= 200:
        sample_score = 10
    elif pitches >= 500 and bip >= 100:
        sample_score = 7
    elif pitches >= 200 and bip >= 50:
        sample_score = 4
    else:
        sample_score = 1

    raw_score = (
        power_score * 0.45 +
        contact_shape_score * 0.20 +
        launch_angle_score * 1.2 +
        sample_score * 1.5 -
        discipline_penalty
    )

    return round(clamp(raw_score), 1)