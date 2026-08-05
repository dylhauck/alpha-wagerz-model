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


def inverse_scale(value, elite, bad):
    if bad == elite:
        return 50

    return clamp(
        ((bad - value) / (bad - elite)) * 100
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


def interaction_bonus(hitter, pitcher):
    bonus = 0

    hitter_xcon = f(hitter.get("xwOBAcon"))
    hitter_barrel = f(hitter.get("Brl/BIP%"))
    hitter_pulled_barrel = f(hitter.get("PulledBrl%"))
    hitter_hard_hit = f(hitter.get("HH%"))
    hitter_fly_ball = f(hitter.get("FB%"))
    hitter_launch_angle = f(hitter.get("LA"))

    pitcher_xwoba = f(pitcher.get("xwOBA"))
    pitcher_barrel = f(pitcher.get("Brl/BIP%"))
    pitcher_hard_hit = f(pitcher.get("HH%"))
    pitcher_fly_ball = f(pitcher.get("FB%"))
    pitcher_swinging_strike = f(pitcher.get("SwStr%"))
    pitcher_hr9 = f(pitcher.get("HR/9"))

    if hitter_barrel >= 14 and pitcher_barrel >= 11:
        bonus += 7

    if hitter_hard_hit >= 48 and pitcher_hard_hit >= 42:
        bonus += 5

    if hitter_fly_ball >= 30 and pitcher_fly_ball >= 33:
        bonus += 4

    if hitter_pulled_barrel >= 7 and pitcher_barrel >= 10:
        bonus += 4

    if hitter_xcon >= 0.410 and pitcher_xwoba >= 0.340:
        bonus += 5

    if (
        12 <= hitter_launch_angle <= 28
        and pitcher_hr9 >= 1.2
    ):
        bonus += 4

    if (
        pitcher_swinging_strike <= 10
        and hitter_barrel >= 12
    ):
        bonus += 4

    return bonus


def score_pitcher(hitter, pitcher):
    if not pitcher:
        return 50

    pitcher_xwoba = f(pitcher.get("xwOBA"))
    pitcher_xwobacon = f(pitcher.get("xwOBAcon"))
    pitcher_barrel = f(pitcher.get("Brl/BIP%"))
    pitcher_hard_hit = f(pitcher.get("HH%"))
    pitcher_fly_ball = f(pitcher.get("FB%"))
    pitcher_swinging_strike = f(pitcher.get("SwStr%"))
    pitcher_ball = f(pitcher.get("Ball%"))
    pitcher_hr9 = f(pitcher.get("HR/9"))

    pitcher_vulnerability = (
        scale(
            pitcher_xwoba,
            0.270,
            0.390,
        )
        * 0.20
        + scale(
            pitcher_xwobacon,
            0.280,
            0.500,
        )
        * 0.18
        + scale(
            pitcher_barrel,
            4.0,
            16.0,
        )
        * 0.22
        + scale(
            pitcher_hard_hit,
            30.0,
            55.0,
        )
        * 0.13
        + scale(
            pitcher_fly_ball,
            20.0,
            45.0,
        )
        * 0.10
        + scale(
            pitcher_hr9,
            0.50,
            2.10,
        )
        * 0.10
        + inverse_scale(
            pitcher_swinging_strike,
            17.0,
            8.0,
        )
        * 0.05
        + scale(
            pitcher_ball,
            28.0,
            40.0,
        )
        * 0.02
    )

    hitter_iso = f(hitter.get("ISO"))
    hitter_xcon = f(hitter.get("xwOBAcon"))
    hitter_barrel = f(hitter.get("Brl/BIP%"))
    hitter_pulled_barrel = f(hitter.get("PulledBrl%"))
    hitter_hard_hit = f(hitter.get("HH%"))
    hitter_fly_ball = f(hitter.get("FB%"))
    hitter_launch_angle = f(hitter.get("LA"))

    hitter_fit = (
        scale(
            hitter_iso,
            0.080,
            0.300,
        )
        * 0.18
        + scale(
            hitter_xcon,
            0.280,
            0.540,
        )
        * 0.18
        + scale(
            hitter_barrel,
            3.0,
            18.0,
        )
        * 0.24
        + scale(
            hitter_pulled_barrel,
            1.0,
            11.0,
        )
        * 0.16
        + scale(
            hitter_hard_hit,
            30.0,
            58.0,
        )
        * 0.10
        + scale(
            hitter_fly_ball,
            18.0,
            45.0,
        )
        * 0.07
        + launch_score(
            hitter_launch_angle
        )
        * 0.07
    )

    score = (
        pitcher_vulnerability * 0.70
        + hitter_fit * 0.30
    )

    score += interaction_bonus(
        hitter,
        pitcher,
    )

    return round(
        clamp(score),
        1,
    )