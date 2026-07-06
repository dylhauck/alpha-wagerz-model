import math


def f(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def scale_score(value, values, floor=20, ceiling=95):
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


def normalize_slate_hitters(games):
    all_hitters = []

    for game in games:
        for side in ["away", "home"]:
            for hitter in game.get("hitters", {}).get(side, []):
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
        power = scale_score(hitter.get("Power"), power_values, 25, 96)
        contact = scale_score(hitter.get("Contact"), contact_values, 25, 92)
        pitcher = scale_score(hitter.get("Pitcher"), pitcher_values, 25, 96)
        pitch_type = scale_score(hitter.get("Pitch Type"), pitch_type_values, 25, 95)
        team = scale_score(hitter.get("Team"), team_values, 35, 88)
        bullpen = scale_score(hitter.get("Bullpen"), bullpen_values, 35, 88)
        weather = scale_score(hitter.get("Weather"), weather_values, 35, 92)
        park = scale_score(hitter.get("Park"), park_values, 35, 92)
        recent = scale_score(hitter.get("Recent"), recent_values, 25, 95)

        matchup = weighted_score([
            (power, 0.24),
            (contact, 0.11),
            (pitcher, 0.25),
            (pitch_type, 0.18),
            (team, 0.06),
            (bullpen, 0.06),
            (weather, 0.05),
            (park, 0.05),
        ])

        ceiling = weighted_score([
            (power, 0.38),
            (pitcher, 0.22),
            (pitch_type, 0.16),
            (weather, 0.08),
            (park, 0.08),
            (recent, 0.08),
        ])

        zone_fit = weighted_score([
            (pitch_type, 0.50),
            (contact, 0.20),
            (pitcher, 0.20),
            (power, 0.10),
        ])

        khr = weighted_score([
            (power, 0.35),
            (pitcher, 0.25),
            (pitch_type, 0.20),
            (park, 0.08),
            (weather, 0.07),
            (recent, 0.05),
        ])

        alpha = weighted_score([
            (matchup, 0.35),
            (ceiling, 0.25),
            (khr, 0.18),
            (recent, 0.14),
            (team, 0.04),
            (bullpen, 0.04),
        ])

        hitter["Power"] = power
        hitter["Contact"] = contact
        hitter["Pitcher"] = pitcher
        hitter["Pitch Type"] = pitch_type
        hitter["Team"] = team
        hitter["Bullpen"] = bullpen
        hitter["Weather"] = weather
        hitter["Park"] = park
        hitter["Recent"] = recent

        hitter["Matchup"] = matchup
        hitter["Test Score"] = matchup
        hitter["Ceiling"] = ceiling
        hitter["Zone Fit"] = zone_fit
        hitter["HR Form"] = recent
        hitter["kHR"] = khr
        hitter["Likely"] = alpha

    return games