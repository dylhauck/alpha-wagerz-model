def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def score_recent_form(hitter):
    hr_form = hitter.get("HR Form")

    if hr_form == "":
        return 50

    try:
        return clamp(float(hr_form))
    except:
        return 50