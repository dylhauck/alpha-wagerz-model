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

    return clamp(
        ((value - bad) / (elite - bad)) * 100
    )


def launch_score(launch_angle):
    if 12 <= launch_angle <= 30:
        return 100

    if (
        8 <= launch_angle < 12
        or 30 < launch_angle <= 36
    ):
        return 75

    if (
        4 <= launch_angle < 8
        or 36 < launch_angle <= 42
    ):
        return 45

    return 20


def score_recent_form(hitter):
    recent_bip = f(
        hitter.get("Recent BIP")
    )

    recent_pitches = f(
        hitter.get("Recent Pitches")
    )

    # Not enough recent data to confidently grade form.
    if recent_bip < 5 and recent_pitches < 30:
        return 50

    recent_iso = scale(
        f(hitter.get("Recent ISO")),
        0.060,
        0.320,
    )

    recent_xwoba = scale(
        f(hitter.get("Recent xwOBA")),
        0.230,
        0.440,
    )

    recent_xwobacon = scale(
        f(hitter.get("Recent xwOBAcon")),
        0.280,
        0.570,
    )

    recent_barrel = scale(
        f(hitter.get("Recent Brl/BIP%")),
        2.0,
        18.0,
    )

    recent_pulled_barrel = scale(
        f(hitter.get("Recent PulledBrl%")),
        0.5,
        10.0,
    )

    recent_hard_hit = scale(
        f(hitter.get("Recent HH%")),
        28.0,
        62.0,
    )

    recent_fly_ball = scale(
        f(hitter.get("Recent FB%")),
        16.0,
        46.0,
    )

    recent_launch = launch_score(
        f(hitter.get("Recent LA"))
    )

    score = (
        recent_iso * 0.24
        + recent_barrel * 0.22
        + recent_pulled_barrel * 0.16
        + recent_xwobacon * 0.14
        + recent_hard_hit * 0.10
        + recent_xwoba * 0.07
        + recent_fly_ball * 0.04
        + recent_launch * 0.03
    )

    # Reduce extreme results when the recent sample is small.
    if recent_bip < 10:
        score = (
            score * 0.70
            + 50 * 0.30
        )
    elif recent_bip < 20:
        score = (
            score * 0.85
            + 50 * 0.15
        )

    return round(
        clamp(score),
        1,
    )

def get_hr_form_trend(hitter):
    recent_bip = f(hitter.get("Recent BIP"))
    recent_pitches = f(hitter.get("Recent Pitches"))

    # Not enough recent data to determine a reliable direction.
    if recent_bip < 5 and recent_pitches < 30:
        return "flat"

    recent_iso = f(hitter.get("Recent ISO"))
    season_iso = f(hitter.get("ISO"))

    recent_brl = f(hitter.get("Recent Brl/BIP%"))
    season_brl = f(hitter.get("Brl/BIP%"))

    recent_hh = f(hitter.get("Recent HH%"))
    season_hh = f(hitter.get("HH%"))

    recent_score = (
        scale(recent_iso, 0.060, 0.320) * 0.45
        + scale(recent_brl, 2.0, 18.0) * 0.35
        + scale(recent_hh, 28.0, 62.0) * 0.20
    )

    baseline_score = (
        scale(season_iso, 0.060, 0.320) * 0.45
        + scale(season_brl, 2.0, 18.0) * 0.35
        + scale(season_hh, 28.0, 62.0) * 0.20
    )

    difference = recent_score - baseline_score

    if difference >= 6:
        return "up"

    if difference <= -6:
        return "down"

    return "flat"