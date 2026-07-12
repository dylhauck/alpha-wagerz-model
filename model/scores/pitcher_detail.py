def safe_float(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low=0, high=100):
    return max(low, min(high, value))

def normalize_score(value, low, high):
    if high <= low:
        return 50

    return clamp(
        ((value - low) / (high - low)) * 100,
        0,
        100,
    )


def score_fly_ball_profile(pitcher):
    pitcher_fb = safe_float(pitcher.get("FB%"))
    pitcher_gb = safe_float(pitcher.get("GB%"))
    pitcher_brl = safe_float(pitcher.get("Brl/BIP%"))
    pitcher_hh = safe_float(pitcher.get("HH%"))

    opp_fb = safe_float(pitcher.get("Opponent FB%"), 27)
    opp_la = safe_float(pitcher.get("Opponent LA"), 16)
    opp_hh = safe_float(pitcher.get("Opponent HH%"), 39)

    score = (
        pitcher_fb * 1.35
        - pitcher_gb * 0.95
        + pitcher_brl * 1.75
        + pitcher_hh * 0.45
        + opp_fb * 1.20
        + opp_la * 1.85
        + opp_hh * 0.65
        - 35
    )

    return round(clamp(score, 5, 70), 1)


def score_barrel_profile(pitcher):
    pitcher_brl = safe_float(pitcher.get("Brl/BIP%"))
    pitcher_hh = safe_float(pitcher.get("HH%"))
    pitcher_xwobacon = safe_float(pitcher.get("xwOBAcon"))
    pitcher_hr9 = safe_float(pitcher.get("HR/9"))

    opponent_brl = safe_float(
        pitcher.get("Opponent Brl/BIP%"),
        8,
    )
    opponent_pulled_brl = safe_float(
        pitcher.get("Opponent PulledBrl%"),
        4,
    )
    opponent_hh = safe_float(
        pitcher.get("Opponent HH%"),
        39,
    )
    opponent_xwobacon = safe_float(
        pitcher.get("Opponent xwOBAcon"),
        0.360,
    )

    pitcher_profile = (
        normalize_score(pitcher_brl, 2, 16) * 0.40
        + normalize_score(pitcher_hh, 25, 55) * 0.20
        + normalize_score(pitcher_xwobacon, 0.250, 0.475) * 0.25
        + normalize_score(pitcher_hr9, 0.25, 2.25) * 0.15
    )

    matchup_profile = (
        normalize_score(opponent_brl, 2, 16) * 0.40
        + normalize_score(opponent_pulled_brl, 0.5, 10) * 0.25
        + normalize_score(opponent_hh, 25, 55) * 0.15
        + normalize_score(opponent_xwobacon, 0.250, 0.475) * 0.20
    )

    score = (
        pitcher_profile * 0.60
        + matchup_profile * 0.40
    )

    return round(clamp(score, 5, 95), 1)


def score_hr_vulnerability(pitcher):
    hr9 = safe_float(pitcher.get("HR/9"))
    pitcher_brl = safe_float(pitcher.get("Brl/BIP%"))
    pitcher_hh = safe_float(pitcher.get("HH%"))
    pitcher_fb = safe_float(pitcher.get("FB%"))
    pitcher_xwobacon = safe_float(pitcher.get("xwOBAcon"))

    opp_iso = safe_float(pitcher.get("Opponent ISO"), 0.150)
    opp_xwoba = safe_float(pitcher.get("Opponent xwOBA"), 0.315)
    opp_brl = safe_float(pitcher.get("Opponent Brl/BIP%"), 8)
    opp_hh = safe_float(pitcher.get("Opponent HH%"), 39)
    opp_fb = safe_float(pitcher.get("Opponent FB%"), 27)

    pitcher_risk = (
        hr9 * 14
        + pitcher_brl * 1.15
        + pitcher_hh * 0.22
        + pitcher_fb * 0.12
        + (pitcher_xwobacon - 0.300) * 80
    )

    matchup_risk = (
        opp_iso * 85
        + (opp_xwoba - 0.290) * 85
        + opp_brl * 1.05
        + opp_hh * 0.18
        + opp_fb * 0.10
    )

    score = pitcher_risk * 0.60 + matchup_risk * 0.40

    return round(clamp(score, 5, 95), 1)


def score_strikeout_score(pitcher):
    swstr = safe_float(pitcher.get("SwStr%"))
    csw = safe_float(pitcher.get("CSW%"))
    ball = safe_float(pitcher.get("Ball%"))
    k_rate = safe_float(pitcher.get("K%"))

    opp_k = safe_float(pitcher.get("Opponent K Score"), 50)
    opp_swstr = safe_float(pitcher.get("Opponent SwStr%"), 10)
    matchup = safe_float(pitcher.get("Matchup Score"), 50)

    pitcher_score = (
        swstr * 2.15
        + csw * 1.25
        - ball * 0.30
        + k_rate * 0.30
    )

    matchup_score = (
        matchup * 0.55
        + opp_k * 0.30
        + opp_swstr * 1.50
    )

    score = pitcher_score * 0.55 + matchup_score * 0.45

    return round(clamp(score, 5, 95), 1)


def score_pitch_score(pitcher):
    xwoba = safe_float(pitcher.get("xwOBA"))
    brl_profile = safe_float(pitcher.get("Barrel Profile"))
    hr_vuln = safe_float(pitcher.get("HR Vulnerability"))
    fb_profile = safe_float(pitcher.get("Fly Ball Profile"))
    ball = safe_float(pitcher.get("Ball%"))
    swstr = safe_float(pitcher.get("SwStr%"))
    k_score = safe_float(pitcher.get("Strikeout Score"))

    opp_xwoba = safe_float(pitcher.get("Opponent xwOBA"), 0.315)
    opp_matchup = safe_float(pitcher.get("Opponent Matchup Score"), 50)

    score = (
        72
        - xwoba * 70
        - opp_xwoba * 45
        - brl_profile * 0.18
        - hr_vuln * 0.16
        - fb_profile * 0.08
        - ball * 0.18
        + swstr * 0.45
        + k_score * 0.16
        + opp_matchup * 0.10
    )

    return round(clamp(score, 5, 95), 1)


def attach_pitcher_detail_scores(pitcher):
    pitcher["Fly Ball Profile"] = score_fly_ball_profile(pitcher)
    pitcher["Barrel Profile"] = score_barrel_profile(pitcher)
    pitcher["HR Vulnerability"] = score_hr_vulnerability(pitcher)
    pitcher["Strikeout Score"] = score_strikeout_score(pitcher)
    pitcher["Pitch Score"] = score_pitch_score(pitcher)

    return pitcher