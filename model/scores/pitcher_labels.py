def safe_float(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def pitcher_risk_label(pitcher):
    hr_vuln = safe_float(pitcher.get("HR Vulnerability"))
    brl = safe_float(pitcher.get("Brl/BIP%"))
    fb = safe_float(pitcher.get("FB%"))

    if hr_vuln >= 50 or brl >= 10.0 or fb >= 48:
        return "High HR Risk"

    if hr_vuln >= 30 or brl >= 7.5 or fb >= 40:
        return "Moderate HR Risk"

    return "Low HR Risk"

def strikeout_label(pitcher):
    k_score = safe_float(pitcher.get("Strikeout Score"))

    if k_score >= 75:
        return "Elite K Upside"
    if k_score >= 60:
        return "Positive K Upside"
    if k_score <= 40:
        return "Low K Upside"
    return "Neutral K Upside"


def pitcher_summary(pitcher):
    return f'{pitcher_risk_label(pitcher)} / {strikeout_label(pitcher)}'


def attach_pitcher_labels(pitcher):
    pitcher["HR Risk"] = pitcher_risk_label(pitcher)
    pitcher["K Upside"] = strikeout_label(pitcher)
    pitcher["Pitcher Notes"] = pitcher_summary(pitcher)
    return pitcher