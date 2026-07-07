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


def launch_score(la):
    if 12 <= la <= 30:
        return 100
    if 8 <= la < 12 or 30 < la <= 36:
        return 75
    if 4 <= la < 8 or 36 < la <= 42:
        return 45
    return 20


def score_recent_form(hitter):
    recent_bip = f(hitter.get("Recent BIP"))
    recent_pitches = f(hitter.get("Recent Pitches"))

    if recent_bip < 5 and recent_pitches < 30:
        return 50

    recent_iso = f(hitter.get("Recent ISO"))
    recent_xwoba = f(hitter.get("Recent xwOBA"))
    recent_xcon = f(hitter.get("Recent xwOBAcon"))
    recent_pulled = f(hitter.get("Recent PulledBrl%"))
    recent_brl = f(hitter.get("Recent Brl/BIP%"))
    recent_hh = f(hitter.get("Recent HH%"))
    recent_fb = f(hitter.get("Recent FB%"))
    recent_la = f(hitter.get("Recent LA"))

    score = (
        scale(recent_iso, 0.070, 0.300) * 0.18 +
        scale(recent_xwoba, 0.240, 0.430) * 0.18 +
        scale(recent_xcon, 0.300, 0.560) * 0.18 +
        scale(recent_brl, 3.0, 16.0) * 0.16 +
        scale(recent_pulled, 1.0, 9.0) * 0.12 +
        scale(recent_hh, 30.0, 60.0) * 0.10 +
        scale(recent_fb, 18.0, 45.0) * 0.05 +
        launch_score(recent_la) * 0.03
    )

    return round(clamp(score), 1)
