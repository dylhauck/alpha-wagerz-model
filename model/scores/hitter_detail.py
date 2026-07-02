def safe_float(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def score_matchup(hitter):
    pitcher = safe_float(hitter.get("Pitcher", 50), 50)
    pitch_type = safe_float(hitter.get("Pitch Type", 50), 50)
    bullpen = safe_float(hitter.get("Bullpen", 50), 50)

    return round(clamp(
        pitcher * 0.45 +
        pitch_type * 0.40 +
        bullpen * 0.15
    ), 1)


def score_ceiling(hitter):
    iso = safe_float(hitter.get("ISO"))
    xwoba_con = safe_float(hitter.get("xwOBAcon"))
    brl = safe_float(hitter.get("Brl/BIP%"))
    hh = safe_float(hitter.get("HH%"))
    fb = safe_float(hitter.get("FB%"))
    la = safe_float(hitter.get("LA"))

    launch_bonus = 4 if 15 <= la <= 32 else 0

    raw = (
        iso * 80 +
        xwoba_con * 45 +
        brl * 1.15 +
        hh * 0.30 +
        fb * 0.18 +
        launch_bonus
    )

    return round(clamp(raw, 0, 97), 1)


def score_zone_fit(hitter):
    pitch_type = safe_float(hitter.get("Pitch Type", 50), 50)
    sweet_spot = safe_float(hitter.get("Sweet Spot%"))
    la = safe_float(hitter.get("LA"))
    fb = safe_float(hitter.get("FB%"))

    la_bonus = 10 if 12 <= la <= 32 else 0

    return round(clamp(
        pitch_type * 0.45 +
        sweet_spot * 0.25 +
        fb * 0.20 +
        la_bonus
    ), 1)


def score_hr_form(hitter):
    recent = safe_float(hitter.get("Recent", 50), 50)
    brl = safe_float(hitter.get("Brl/BIP%"))
    hh = safe_float(hitter.get("HH%"))
    iso = safe_float(hitter.get("ISO"))

    return round(clamp(
        recent * 0.35 +
        brl * 1.4 +
        hh * 0.45 +
        iso * 90
    ), 1)


def score_khr(hitter):
    swstr = safe_float(hitter.get("SwStr%"))
    contact = safe_float(hitter.get("Contact", 50), 50)
    power = safe_float(hitter.get("Power", 50), 50)

    # Higher = better HR profile with less strikeout drag
    return round(clamp(
        power * 0.55 +
        contact * 0.35 -
        swstr * 0.75 +
        10
    ), 1)


def score_test_score(hitter):
    matchup = score_matchup(hitter)
    ceiling = score_ceiling(hitter)
    zone_fit = score_zone_fit(hitter)
    hr_form = score_hr_form(hitter)
    khr = score_khr(hitter)

    return round(clamp(
        matchup * 0.25 +
        ceiling * 0.25 +
        zone_fit * 0.20 +
        hr_form * 0.20 +
        khr * 0.10
    ), 1)


def attach_hitter_detail_scores(hitter):
    hitter["Matchup"] = score_matchup(hitter)
    hitter["Ceiling"] = score_ceiling(hitter)
    hitter["Zone Fit"] = score_zone_fit(hitter)
    hitter["HR Form"] = score_hr_form(hitter)
    hitter["kHR"] = score_khr(hitter)
    hitter["Test Score"] = score_test_score(hitter)

    return hitter