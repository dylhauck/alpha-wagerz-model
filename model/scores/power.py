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


def score_power(hitter):
    iso = f(hitter.get("ISO"))
    xwobacon = f(hitter.get("xwOBAcon"))
    barrel = f(hitter.get("Brl/BIP%"))
    pulled_barrel = f(hitter.get("PulledBrl%"))
    hard_hit = f(hitter.get("HH%"))
    fly_ball = f(hitter.get("FB%"))
    launch_angle = f(hitter.get("LA"))

    score = (
        scale(iso, 0.080, 0.300) * 0.22
        + scale(xwobacon, 0.280, 0.540) * 0.18
        + scale(barrel, 3.0, 18.0) * 0.24
        + scale(pulled_barrel, 1.0, 11.0) * 0.16
        + scale(hard_hit, 30.0, 58.0) * 0.10
        + scale(fly_ball, 18.0, 45.0) * 0.05
        + launch_score(launch_angle) * 0.05
    )

    return round(
        clamp(score),
        1,
    )