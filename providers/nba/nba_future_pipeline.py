from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'processed' / 'nba'
NEXT = DATA / 'next'
WEB = ROOT.parent / 'alpha-wagerz-web' / 'public' / 'data' / 'nba'
WEB_NEXT = WEB / 'next'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'  Saved {path}')


@contextmanager
def overridden(module, **changes):
    old = {}
    for name, value in changes.items():
        if not hasattr(module, name):
            raise AttributeError(f'{module.__name__} has no {name}; provider changed, check compatibility')
        old[name] = getattr(module, name)
        setattr(module, name, value)
    try:
        yield
    finally:
        for name, value in old.items():
            setattr(module, name, value)


def require(path):
    if not path.is_file():
        raise FileNotFoundError(f'Missing required file: {path}')


def publish_shared():
    # Historical player and team stats are league-wide, not slate-specific.
    for name in ('teams.json', 'team_stats.json', 'team_rankings.json', 'player_stats.json'):
        source = DATA / name
        if source.is_file():
            shutil.copy2(source, NEXT / name)
            shutil.copy2(source, WEB_NEXT / name)
    # Player matchup builder already writes next/player_matchups.json.
    path = NEXT / 'player_matchups.json'
    if path.is_file():
        shutil.copy2(path, WEB_NEXT / 'player_matchups.json')


def future_injuries(slate):
    source = DATA / 'injuries.json'
    if not source.exists():
        print('  Injuries unavailable: run python -m providers.nba.nba_injuries first')
        return
    payload = read(source)
    # The existing injury provider emits all NBA injuries, not only current-slate teams.
    teams = {str(g.get(k) or '').upper() for g in slate.get('games', [])
             for k in ('away_abbr', 'home_abbr', 'away_team', 'home_team')}
    injuries = payload.get('injuries', [])
    filtered = [row for row in injuries if str(row.get('team', '')).upper() in teams]
    output = dict(payload)
    output.update(slate_type='future', slate_date=slate.get('slate_date'),
                  games=slate.get('games', []), injuries=filtered,
                  slate_injury_count=len(filtered), injury_count=len(filtered))
    write(NEXT / 'injuries.json', output)
    write(WEB_NEXT / 'injuries.json', output)


def projections():
    import model.nba.betting_projections as betting
    with overridden(betting,
                    SLATE_PATH=NEXT / 'slate.json',
                    PLAYER_MATCHUPS_PATH=NEXT / 'player_matchups.json',
                    OUTPUT_PATH=NEXT / 'betting_projections.json',
                    WEB_OUTPUT_PATH=WEB_NEXT / 'betting_projections.json'):
        betting.build_nba_betting_projections()

    import model.nba.build_nba_period_projections as periods
    try:
        with overridden(periods,
                        SOURCE=NEXT / 'betting_projections.json',
                        OUT=NEXT / 'team_projections.json',
                        WEB=WEB_NEXT / 'team_projections.json'):
            periods.main()
    except Exception as exc:
        # NBA stats frequently times out on GitHub-hosted runners.
        # Preserve existing projections rather than publish invented numbers.
        # Continue to build independent live markets and player props.
        print(
            f"WARNING: Future NBA period projections unavailable: {exc}. "
            "Preserving any existing period projection data.",
            flush=True,
        )


def markets():
    import providers.nba.nba_live_markets as live
    # The existing provider resolves its slate using MODEL / 'slate.json'.
    # Point its model and web directories to the future slate only.
    with overridden(live, MODEL=NEXT, WEB=WEB_NEXT):
        live.main()


def main():
    NEXT.mkdir(parents=True, exist_ok=True)
    WEB_NEXT.mkdir(parents=True, exist_ok=True)
    require(NEXT / 'slate.json')
    require(DATA / 'team_stats.json')
    require(DATA / 'team_rankings.json')
    require(DATA / 'player_stats.json')
    require(NEXT / 'player_matchups.json')
    slate = read(NEXT / 'slate.json')
    if not slate.get('games'):
        print('No future NBA games available. Skipping projections and odds.')
        return
    print(f"Future NBA slate: {slate.get('slate_date')} | {len(slate['games'])} games")
    publish_shared()
    future_injuries(slate)
    print('\nBuilding future NBA betting projections...')
    projections()
    print('\nFetching future NBA sportsbook markets and player props...')
    try:
        markets()
    except Exception as exc:
        # Do not misrepresent missing markets as valid betting data.
        print(f'WARNING: Future sportsbook markets unavailable: {exc}')
        raise
    print('\nNBA FUTURE SLATE COMPLETE — current-slate outputs were not changed.')


if __name__ == '__main__':
    main()
