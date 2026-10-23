from __future__ import annotations

import gzip
from providers.odds_bulk import fetch_many
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
MODEL = ROOT / 'data' / 'processed' / 'nba'
WEB = ROOT.parent / 'alpha-wagerz-web' / 'public' / 'data' / 'nba'
API_KEY = os.getenv('ODDS_API_IO_KEY')
BASE = os.getenv('ODDS_API_IO_BASE', 'https://api.odds-api.io/v3').rstrip('/')
BOOKS = [x.strip() for x in os.getenv('NBA_ODDS_API_IO_BOOKMAKERS', 'FanDuel,DraftKings').split(',') if x.strip()]
DEBUG = os.getenv('NBA_MARKETS_DEBUG', '0') == '1'
# Cap concurrency to protect the provider and keep request behavior predictable.
ODDS_WORKERS = max(1, min(6, int(os.getenv('NBA_ODDS_WORKERS', '4'))))

ALIASES = {'ATL':'Atlanta Hawks','BOS':'Boston Celtics','BKN':'Brooklyn Nets','CHA':'Charlotte Hornets','CHI':'Chicago Bulls','CLE':'Cleveland Cavaliers','DAL':'Dallas Mavericks','DEN':'Denver Nuggets','DET':'Detroit Pistons','GSW':'Golden State Warriors','HOU':'Houston Rockets','IND':'Indiana Pacers','LAC':'Los Angeles Clippers','LAL':'Los Angeles Lakers','MEM':'Memphis Grizzlies','MIA':'Miami Heat','MIL':'Milwaukee Bucks','MIN':'Minnesota Timberwolves','NOP':'New Orleans Pelicans','NYK':'New York Knicks','OKC':'Oklahoma City Thunder','ORL':'Orlando Magic','PHI':'Philadelphia 76ers','PHX':'Phoenix Suns','POR':'Portland Trail Blazers','SAC':'Sacramento Kings','SAS':'San Antonio Spurs','TOR':'Toronto Raptors','UTA':'Utah Jazz','WAS':'Washington Wizards'}

def norm(value):
    return re.sub(r'[^a-z0-9]', '', str(value or '').lower().replace('&', 'and'))

def team(value):
    n = norm(value)
    for abbr, full in ALIASES.items():
        if n in (norm(abbr), norm(full)):
            return abbr
    return str(value or '')

def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def first(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        result = number(obj.get(key))
        if result is not None:
            return result
    return None

def american(value):
    v = number(value)
    if v is None:
        return None
    if v >= 100 or v <= -100:
        return round(v)
    if v >= 2:
        return round((v - 1) * 100)
    if 1 < v < 2:
        return round(-100 / (v - 1))
    return None

def api_get(endpoint, params):
    url = f'{BASE}/{endpoint.lstrip("/")}?{urlencode(params)}'
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Alpha-Wagerz/1.0'})
    try:
        with urlopen(request, timeout=40) as response:
            raw = response.read()
            if 'gzip' in response.headers.get('Content-Encoding', '').lower() or raw[:2] == b'\x1f\x8b':
                raw = gzip.decompress(raw)
            return json.loads(raw.decode('utf-8'))
    except HTTPError as exc:
        raise RuntimeError(f'HTTP {exc.code}: {exc.read().decode(errors="replace")[:400]}') from exc
    except URLError as exc:
        raise RuntimeError(f'Network error: {exc}') from exc

def event_teams(event):
    def get_team(*keys):
        for key in keys:
            value = event.get(key)
            if isinstance(value, dict):
                value = value.get('name') or value.get('team') or value.get('abbreviation')
            if value:
                return team(value)
        return ''
    return get_team('away', 'awayTeam', 'away_team'), get_team('home', 'homeTeam', 'home_team')

def bookmaker_items(payload):
    raw = payload.get('bookmakers', {}) if isinstance(payload, dict) else {}
    if isinstance(raw, dict):
        return [(name, markets) for name, markets in raw.items() if isinstance(markets, list) and any(norm(name) == norm(b) for b in BOOKS)]
    if isinstance(raw, list):
        return [(str(x.get('name') or x.get('title')), x.get('markets', [])) for x in raw if isinstance(x, dict) and isinstance(x.get('markets'), list) and any(norm(x.get('name') or x.get('title')) == norm(b) for b in BOOKS)]
    return []

def market_name(m):
    return str(m.get('name') or m.get('market') or m.get('type') or m.get('key') or '')

def rows(m):
    raw = m.get('odds', [])
    return [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []

def is_period(name):
    s = name.lower()
    if re.search(r'\b(q[1-4]|quarter|1st half|2nd half|first half|second half|half time|halftime|\bht\b|\b1h\b|\b2h\b)\b', s):
        return True
    return False

def period_key(name):
    s = name.lower()
    for pattern, key in [(r'\bq1\b|first quarter|1st quarter', 'Q1'), (r'\bq2\b|second quarter|2nd quarter', 'Q2'), (r'\bq3\b|third quarter|3rd quarter', 'Q3'), (r'\bq4\b|fourth quarter|4th quarter', 'Q4'), (r'\b2h\b|second half|2nd half', '2H'), (r'\b1h\b|first half|1st half|\bht\b|half time|halftime', '1H')]:
        if re.search(pattern, s):
            return key
    return None

def parse_team(book, markets):
    result = {'bookmaker': book, 'moneyline': None, 'spread': None, 'total': None, 'team_totals': None}
    periods = {}
    for m in markets:
        if not isinstance(m, dict):
            continue
        name = market_name(m).lower()
        if 'player' in name:
            continue
        period = period_key(name)
        target = periods.setdefault(period, {'bookmaker': book, 'moneyline': None, 'spread': None, 'total': None, 'team_totals': None}) if period else result
        for row in rows(m):
            if norm(name) in ('ml', 'moneyline') or 'moneyline' in name or 'match winner' in name or '1x2' in name:
                home, away = first(row, 'home', 'homeOdds', 'home_odds'), first(row, 'away', 'awayOdds', 'away_odds')
                if home is not None and away is not None and target['moneyline'] is None:
                    target['moneyline'] = {'home': american(home), 'away': american(away)}
            elif ('spread' in name or 'handicap' in name) and 'team' not in name:
                line = first(row, 'hdp', 'line', 'point')
                home, away = first(row, 'home', 'homeOdds', 'home_odds'), first(row, 'away', 'awayOdds', 'away_odds')
                if line is not None and home is not None and away is not None and target['spread'] is None:
                    target['spread'] = {'home_line': line, 'away_line': -line, 'home_odds': american(home), 'away_odds': american(away)}
            elif 'team total' in name or 'teamtotal' in norm(name):
                side = 'home' if 'home' in name else 'away' if 'away' in name else None
                line = first(row, 'hdp', 'line', 'point')
                if side and line is not None:
                    if target['team_totals'] is None:
                        target['team_totals'] = {}
                    if side not in target['team_totals']:
                        target['team_totals'][side] = line
            elif ('total' in name or 'over/under' in name) and 'team' not in name:
                line = first(row, 'hdp', 'line', 'point')
                over, under = first(row, 'over', 'overOdds', 'over_odds'), first(row, 'under', 'underOdds', 'under_odds')
                over_price, under_price = american(over), american(under)
                # Providers can return alternate game totals alongside the
                # main line (e.g. 205.5 at -10000/+2500 instead of ~240).
                # Prefer a two-sided, competitively priced main market; never
                # select the first alternate solely because it appears first.
                if (line is not None and over_price is not None and
                        under_price is not None):
                    candidate = {'line': line, 'over_odds': over_price,
                                 'under_odds': under_price}
                    current = target['total']
                    def quality(total):
                        o, u = total['over_odds'], total['under_odds']
                        # Both prices near even odds indicates the primary
                        # total. This is a selection criterion, not a model
                        # projection or a fabricated sportsbook line.
                        return abs(o + 110) + abs(u + 110)
                    if (current is None or
                            quality(candidate) < quality(current)):
                        target['total'] = candidate
    return result, periods

PROP_TYPES = {
    'ptsrebsasts': 'pra', 'pointsreboundsassists': 'pra',
    'ptsrebs': 'pr', 'pointsrebounds': 'pr',
    'ptsasts': 'pa', 'pointsassists': 'pa',
    'rebsasts': 'ra', 'reboundsassists': 'ra',
    '3pointfg': 'fg3m', '3pointers': 'fg3m', '3ptfg': 'fg3m',
    'points': 'pts', 'rebounds': 'reb', 'assists': 'ast',
    'steals': 'stl', 'blocks': 'blk', 'turnovers': 'tov',
    'stealsblocks': 'stocks', 'doubledouble': 'dd', 'tripledouble': 'td',
}

def classify(value):
    key = norm(value)
    if key.startswith('player'):
        key = key[6:]
    return PROP_TYPES.get(key)

def parse_props(book, markets, event_id, game_id):
    props = []
    seen = set()
    for market in markets:
        if not isinstance(market, dict):
            continue
        name = market_name(market)
        if 'player' not in name.lower() and not classify(name):
            continue
        for row in rows(market):
            label = str(row.get('label') or row.get('name') or '').strip()
            match = re.match(r'^\s*(.*?)\s*\(([^()]*)\)\s*$', label)
            if match:
                player, stat = match.group(1).strip(), match.group(2).strip()
                prop_type = classify(stat)
            else:
                player = str(row.get('player_name') or row.get('playerName') or row.get('player') or label).strip()
                prop_type = classify(row.get('prop_type') or row.get('stat') or name)
            if not prop_type or not player or norm(player) == 'anyplayer':
                continue
            line = first(row, 'hdp', 'line', 'point')
            over = first(row, 'over', 'overOdds', 'over_odds')
            under = first(row, 'under', 'underOdds', 'under_odds')
            if line is None or (over is None and under is None):
                continue
            identifier = (norm(player), prop_type, line, norm(book))
            if identifier in seen:
                continue
            seen.add(identifier)
            props.append({
                'player_name': player, 'prop_type': prop_type, 'line': line,
                'over_odds': american(over), 'under_odds': american(under),
                'sportsbook': book, 'event_id': event_id, 'game_id': game_id,
                'market_name': stat if match else name,
            })
    return props

def score_market(m):
    return sum(m.get(k) is not None for k in ('moneyline', 'spread', 'total', 'team_totals'))

def merge_market(current, candidate):
    if not current:
        return dict(candidate)
    for key in ('moneyline', 'spread', 'total', 'team_totals'):
        if key == 'team_totals' and candidate.get(key):
            if not isinstance(current.get(key), dict):
                current[key] = {}
            current[key].update({side: line for side, line in candidate[key].items() if side not in current[key]})
        elif current.get(key) is None and candidate.get(key) is not None:
            current[key] = candidate[key]
    if not current.get('bookmaker'):
        current['bookmaker'] = candidate.get('bookmaker')
    return current

def main():
    if not API_KEY:
        raise SystemExit('Missing ODDS_API_IO_KEY in model root .env')
    now = datetime.now(timezone.utc)
    events = api_get('events', {'apiKey': API_KEY, 'sport': 'basketball', 'league': 'usa-nba', 'status': 'pending', 'from': (now - timedelta(hours=2)).isoformat(), 'to': (now + timedelta(days=2)).isoformat()})
    if isinstance(events, dict):
        events = events.get('events', [])
    if not isinstance(events, list):
        raise RuntimeError('Unexpected Odds-API.io events response')
    slate_path = MODEL / 'slate.json'
    if not slate_path.exists():
        raise SystemExit(f'Missing slate: {slate_path}')
    slate = json.loads(slate_path.read_text(encoding='utf-8'))
    slate_games = slate if isinstance(slate, list) else slate.get('games', [])
    matched = {}
    for game in slate_games:
        if isinstance(game, dict):
            matched[(team(game.get('away_abbr') or game.get('away_team')), team(game.get('home_abbr') or game.get('home_team')))] = game
    # Fetch independent events concurrently, then parse in original event order.
    # This preserves output schemas and avoids concurrent writes to output files.
    targets = []
    for event in events:
        if not isinstance(event, dict):
            continue
        away, home = event_teams(event)
        game = matched.get((away, home))
        event_id = event.get('id') or event.get('eventId')
        if game is not None and event_id:
            targets.append((away, home, game, event_id))

    def fetch_single(event_id):
        return api_get('odds', {
            'apiKey': API_KEY,
            'eventId': event_id,
            'bookmakers': ','.join(BOOKS),
        })

    def fetch_multi(event_ids):
        return api_get('odds/multi', {
            'apiKey': API_KEY,
            'eventIds': ','.join(event_ids),
            'bookmakers': ','.join(BOOKS),
        })

    odds_by_event = fetch_many(
        [target[3] for target in targets],
        fetch_single,
        fetch_multi,
        workers=ODDS_WORKERS,
    )
    teams_out, props_out = [], []
    for away, home, game, event_id in targets:
        data = odds_by_event.get(str(event_id))
        if not isinstance(data, dict):
            print(f'WARN {away} @ {home}: odds unavailable', flush=True)
            continue
        if 'bookmakers' not in data and isinstance(data.get('data'), dict):
            data = data['data']
        book_items = bookmaker_items(data)
        output = {'game_id': game.get('game_id'), 'event_id': event_id, 'away_team': away, 'home_team': home, 'full_game': {}, 'periods': {}}
        for book in BOOKS:
            entry = next(((b, ms) for b, ms in book_items if norm(b) == norm(book)), None)
            if not entry:
                continue
            book_name, markets = entry
            full, periods = parse_team(book_name, markets)
            output['full_game'] = merge_market(output['full_game'], full)
            for key, market in periods.items():
                output['periods'][key] = merge_market(output['periods'].get(key), market)
            found_props = parse_props(book_name, markets, event_id, game.get('game_id'))
            props_out.extend(found_props)
            print(f'  {book_name}: {len(markets)} markets | {len(found_props)} parsed player props')
            if DEBUG:
                for m in markets:
                    if isinstance(m, dict):
                        print('    ', market_name(m), '| odds rows:', len(rows(m)))
                if not found_props:
                    sample = next((m for m in markets if isinstance(m, dict) and ('player' in market_name(m).lower() or classify(market_name(m)))), None)
                    if sample:
                        print('    UNPARSED PLAYER MARKET SAMPLE:', json.dumps(sample, ensure_ascii=False)[:5000])
        teams_out.append(output)
        print(f'{away} @ {home}: ML={bool(output["full_game"].get("moneyline"))}, spread={bool(output["full_game"].get("spread"))}, total={bool(output["full_game"].get("total"))}, team_totals={output["full_game"].get("team_totals")}, props={sum(p["event_id"] == event_id for p in props_out)}', flush=True)
    team_payload = {'generated_at': now.isoformat(), 'games': teams_out}
    prop_payload = {'generated_at': now.isoformat(), 'props': props_out}
    for directory in (MODEL, WEB):
        directory.mkdir(parents=True, exist_ok=True)
        for filename, payload in [('live_team_markets.json', team_payload), ('player_prop_markets.json', prop_payload)]:
            path = directory / filename
            path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            print(f'Saved {path}', flush=True)
    print(f'Games: {len(teams_out)} | player props: {len(props_out)}', flush=True)
    if not props_out:
        print('NOTE: No recognizable player prop rows returned. Run with NBA_MARKETS_DEBUG=1 to inspect market shapes.', flush=True)

if __name__ == '__main__':
    main()
