from model.scores.recent_form import get_hr_form_trend

def f(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def scale_score(value, values, floor=35, ceiling=95):
    nums = [f(v, None) for v in values]
    nums = [v for v in nums if v is not None]

    if not nums:
        return 50

    low = min(nums)
    high = max(nums)

    if high == low:
        return 50

    scaled = floor + ((f(value) - low) / (high - low)) * (ceiling - floor)
    return round(clamp(scaled), 1)


def weighted_score(parts):
    total_weight = sum(weight for _, weight in parts)
    if total_weight == 0:
        return 50

    total = sum(f(value, 50) * weight for value, weight in parts)
    return round(clamp(total / total_weight), 1)


def boost_elite(score, midpoint=62, strength=1.22):
    score = f(score, 50)

    if score <= midpoint:
        return round(score, 1)

    boosted = midpoint + ((score - midpoint) * strength)
    return round(clamp(boosted), 1)


def get_game_hitters(game, side):
    hitters = game.get("hitters", {})

    if isinstance(hitters, dict):
        return hitters.get(side, [])

    if side == "away":
        return game.get("away_hitters", [])

    if side == "home":
        return game.get("home_hitters", [])

    return []

def score_hr_arsenal_fit(hitter, fallback=50):
    """
    Build an HR-specific arsenal score from today's opposing
    pitch mix and the hitter's pitch-family matchup results.
    """

    pitch_type_score = f(
        hitter.get("Pitch Type Score"),
        fallback,
    )

    fastball = f(
        hitter.get("Fastball Matchup"),
        None,
    )

    breaking = f(
        hitter.get("Breaking Ball Matchup"),
        None,
    )

    offspeed = f(
        hitter.get("Offspeed Matchup"),
        None,
    )

    xhr_matchup = f(
        hitter.get("xHR Matchup"),
        None,
    )

    family_scores = [
        score
        for score in [
            fastball,
            breaking,
            offspeed,
        ]
        if score is not None
    ]

    if family_scores:
        average_family = (
            sum(family_scores) /
            len(family_scores)
        )

        best_family = max(family_scores)
    else:
        average_family = pitch_type_score
        best_family = pitch_type_score

    # xHR Matchup is stored on a much smaller scale than
    # the 0–100 matchup scores, so convert it to 0–100.
    if xhr_matchup is None:
        xhr_score = pitch_type_score
    else:
        xhr_score = clamp(
            xhr_matchup * 10,
            0,
            100,
        )

    arsenal_fit = weighted_score([
        (pitch_type_score, 0.40),
        (average_family, 0.20),
        (best_family, 0.20),
        (xhr_score, 0.20),
    ])

    return round(
        clamp(arsenal_fit),
        1,
    )

def normalize_slate_hitters(games):
    all_hitters = []

    for game in games:
        for side in ["away", "home"]:
            for hitter in get_game_hitters(game, side):
                all_hitters.append(hitter)

    if not all_hitters:
        return games

    power_values = [h.get("Power") for h in all_hitters]
    contact_values = [h.get("Contact") for h in all_hitters]
    pitcher_values = [h.get("Pitcher") for h in all_hitters]
    pitch_type_values = [h.get("Pitch Type") for h in all_hitters]
    team_values = [h.get("Team") for h in all_hitters]
    bullpen_values = [h.get("Bullpen") for h in all_hitters]
    weather_values = [h.get("Weather") for h in all_hitters]
    park_values = [h.get("Park") for h in all_hitters]
    recent_values = [h.get("Recent") for h in all_hitters]

    for hitter in all_hitters:
        power = scale_score(hitter.get("Power"), power_values, 35, 98)
        contact = scale_score(hitter.get("Contact"), contact_values, 35, 92)
        pitcher = scale_score(hitter.get("Pitcher"), pitcher_values, 35, 98)
        pitch_type = scale_score(hitter.get("Pitch Type"), pitch_type_values, 35, 96)
        team = scale_score(hitter.get("Team"), team_values, 40, 90)
        bullpen = scale_score(hitter.get("Bullpen"), bullpen_values, 40, 90)
        weather = scale_score(hitter.get("Weather"), weather_values, 40, 92)
        park = scale_score(hitter.get("Park"), park_values, 40, 92)
        recent = scale_score(hitter.get("Recent"), recent_values, 30, 95)

        hr_arsenal_fit = score_hr_arsenal_fit(
           hitter,
            fallback=pitch_type,
        )

        matchup = weighted_score([
            (power, 0.10),
            (pitcher, 0.52),
            (pitch_type, 0.20),
            (contact, 0.10),
            (recent, 0.05),
            (bullpen, 0.04),
            (weather, 0.015),
            (park, 0.015),
        ])

        matchup = boost_elite(matchup, midpoint=60, strength=1.35)

        ceiling = weighted_score([
            (power, 0.35),
            (pitcher, 0.25),
            (pitch_type, 0.15),
            (weather, 0.10),
            (park, 0.10),
            (recent, 0.05),
        ])

        ceiling = boost_elite(ceiling, midpoint=62, strength=1.25)

        zone_fit = weighted_score([
            (pitch_type, 0.60),
            (pitcher, 0.25),
            (contact, 0.10),
            (power, 0.05),
        ])

        khr = weighted_score([
    # Today's specific opposing-pitcher vulnerability.
    (pitcher, 0.30),

    # Detailed arsenal and pitch-family HR fit.
    (hr_arsenal_fit, 0.30),

    # Overall pitch-type score remains relevant.
    (pitch_type, 0.15),

    # Raw power matters, but no longer dominates.
    (power, 0.15),

    # Current HR form.
    (recent, 0.05),

    # Game environment.
    (park, 0.025),
    (weather, 0.025),
])
        khr = boost_elite(khr, midpoint=60, strength=1.30)

        alpha = weighted_score([
            (matchup, 0.25),
            (zone_fit, 0.25),
            (ceiling, 0.25),
            (khr, 0.15),
            (team, 0.05),
            (bullpen, 0.05),
        ])

        alpha = boost_elite(alpha, midpoint=61, strength=1.22)

        hitter["Power"] = power
        hitter["Contact"] = contact
        hitter["Pitcher"] = pitcher
        hitter["Pitch Type"] = pitch_type
        hitter["Team"] = team
        hitter["Bullpen"] = bullpen
        hitter["Weather"] = weather
        hitter["Park"] = park
        hitter["Recent"] = recent

        hitter["Matchup"] = round(matchup, 1)
        hitter["Test Score"] = round(matchup, 1)
        hitter["Ceiling"] = round(ceiling, 1)
        hitter["Zone Fit"] = round(zone_fit, 1)
        hitter["HR Form"] = round(recent, 1)
        hitter["HR Form Trend"] = get_hr_form_trend(hitter)
        hitter["kHR"] = round(khr, 1)
        hitter["Likely"] = round(alpha, 1)
    return games