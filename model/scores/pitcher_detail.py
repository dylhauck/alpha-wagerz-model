def safe_float(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def score_pitch_score(pitcher):
    xwoba = safe_float(pitcher.get("xwOBA"))
    brl = safe_float(pitcher.get("Brl/BIP%"))
    hh = safe_float(pitcher.get("HH%"))
    fb = safe_float(pitcher.get("FB%"))
    ball = safe_float(pitcher.get("Ball%"))
    swstr = safe_float(pitcher.get("SwStr%"))

    return round(clamp(
        100
        - xwoba * 85
        - brl * 1.2
        - hh * 0.35
        - fb * 0.25
        - ball * 0.20
        + swstr * 0.55
    ), 1)


def score_strikeout_score(pitcher):
    swstr = safe_float(pitcher.get("SwStr%"))
    csw = safe_float(pitcher.get("CSW%"))
    ball = safe_float(pitcher.get("Ball%"))
    k_rate = safe_float(pitcher.get("K%"))

    return round(clamp(
        swstr * 2.4
        + csw * 1.5
        - ball * 0.35
        + k_rate * 0.35
    ), 1)


def score_hr_vulnerability(pitcher):
    hr9 = safe_float(pitcher.get("HR/9"))
    brl = safe_float(pitcher.get("Brl/BIP%"))
    hh = safe_float(pitcher.get("HH%"))
    fb = safe_float(pitcher.get("FB%"))
    xwoba_con = safe_float(pitcher.get("xwOBAcon"))

    return round(clamp(
        hr9 * 10
        + brl * 1.5
        + hh * 0.55
        + fb * 0.35
        + xwoba_con * 60
    ), 1)


def score_fly_ball_profile(pitcher):
    fb = safe_float(pitcher.get("FB%"))
    gb = safe_float(pitcher.get("GB%"))

    return round(clamp(
        50 + fb * 0.75 - gb * 0.35
    ), 1)


def score_barrel_profile(pitcher):
    brl = safe_float(pitcher.get("Brl/BIP%"))
    hh = safe_float(pitcher.get("HH%"))

    return round(clamp(
        brl * 1.7 + hh * 0.55
    ), 1)


def attach_pitcher_detail_scores(pitcher):
    pitcher["Pitch Score"] = score_pitch_score(pitcher)
    pitcher["Strikeout Score"] = score_strikeout_score(pitcher)
    pitcher["HR Vulnerability"] = score_hr_vulnerability(pitcher)
    pitcher["Fly Ball Profile"] = score_fly_ball_profile(pitcher)
    pitcher["Barrel Profile"] = score_barrel_profile(pitcher)

    return pitcher