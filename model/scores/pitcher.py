def score_pitcher(hitter, pitcher):
    if not pitcher:
        return 50

    score = pitcher.get("Pitch Score")

    try:
        return round(100 - float(score), 1)
    except:
        return 50