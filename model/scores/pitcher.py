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


def launch_score(la):
    if 15 <= la <= 28:
        return 100
    if 10 <= la < 15 or 28 < la <= 35:
        return 75
    if 5 <= la < 10 or 35 < la <= 42:
        return 45
    return 20


def score_pitcher(hitter, pitcher):
    if not pitcher:
        return 50

    # Pitcher vulnerability
    p_xwoba = f(pitcher.get("xwOBA"))
    p_brl = f(pitcher.get("Brl/BIP%"))
    p_hh = f(pitcher.get("HH%"))
    p_fb = f(pitcher.get("FB%"))
    p_swstr = f(pitcher.get("SwStr%"))
    p_ball = f(pitcher.get("Ball%"))
    p_hr9 = f(pitcher.get("HR/9"))

    pitcher_vulnerability = (
        scale(p_xwoba, 0.270, 0.390) * 0.28 +
        scale(p_brl, 5.0, 15.0) * 0.20 +
        scale(p_hh, 32.0, 55.0) * 0.16 +
        scale(p_fb, 22.0, 45.0) * 0.12 +
        scale(p_ball, 28.0, 40.0) * 0.08 +
        inverse_scale(p_swstr, 17.0, 8.0) * 0.10 +
        scale(p_hr9, 0.6, 2.0) * 0.06
    )

    # Hitter attack profile
    h_iso = f(hitter.get("ISO"))
    h_xwoba = f(hitter.get("xwOBA"))
    h_xcon = f(hitter.get("xwOBAcon"))
    h_brl = f(hitter.get("Brl/BIP%"))
    h_hh = f(hitter.get("HH%"))
    h_fb = f(hitter.get("FB%"))
    h_la = f(hitter.get("LA"))
    h_swstr = f(hitter.get("SwStr%"))

    hitter_attack = (
        scale(h_iso, 0.080, 0.280) * 0.22 +
        scale(h_xwoba, 0.250, 0.420) * 0.18 +
        scale(h_xcon, 0.280, 0.520) * 0.18 +
        scale(h_brl, 4.0, 18.0) * 0.18 +
        scale(h_hh, 32.0, 60.0) * 0.12 +
        scale(h_fb, 20.0, 45.0) * 0.06 +
        launch_score(h_la) * 0.04 +
        inverse_scale(h_swstr, 6.0, 18.0) * 0.02
    )

    # Combination creates hitter-specific matchup, not same score for every hitter
    score = (
        pitcher_vulnerability * 0.45 +
        hitter_attack * 0.45 +
        ((pitcher_vulnerability + hitter_attack) / 2) * 0.10
    )

    return round(clamp(score), 1)