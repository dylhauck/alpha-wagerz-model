"""Static regression checks for the performance-only odds changes.

These tests deliberately avoid importing provider modules (which require
production dependencies and credentials). Live API integration is separate.
"""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OddsConcurrencyTests(unittest.TestCase):
    def test_provider_modules_compile(self):
        for relative in (
            "providers/mlb/market.py",
            "providers/nfl/nfl_odds.py",
            "providers/nba/nba_live_markets.py",
        ):
            with self.subTest(relative=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                compile(source, relative, "exec")

    def test_provider_uses_shared_bulk_fetcher(self):
        for relative in (
            "providers/mlb/market.py",
            "providers/nfl/nfl_odds.py",
            "providers/nba/nba_live_markets.py",
        ):
            with self.subTest(relative=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("from providers.odds_bulk import fetch_many", source)
                self.assertIn("fetch_many(", source)
                self.assertIn("odds/multi", source)

    def test_bulk_results_are_keyed_by_event_id(self):
        from providers.odds_bulk import fetch_many

        batches = []
        def multi(ids):
            batches.append(ids)
            return [
                {"id": event_id, "bookmakers": {"FanDuel": []}}
                for event_id in reversed(ids)
            ]

        result = fetch_many(
            range(1, 24),
            lambda event_id: self.fail("Unexpected individual fallback"),
            multi,
            workers=2,
        )
        self.assertEqual(len(batches), 3)
        self.assertEqual(len(result), 23)
        self.assertEqual(result["1"]["id"], "1" if isinstance(result["1"]["id"], str) else 1)

    def test_bulk_fallback_for_missing_events(self):
        from providers.odds_bulk import fetch_many
        singles = []
        def single(event_id):
            singles.append(event_id)
            return {"id": event_id, "bookmakers": {}}

        result = fetch_many(
            ["a", "b"],
            single,
            lambda ids: [{"id": "b", "bookmakers": {}}],
            workers=1,
        )
        self.assertEqual(singles, ["a"])
        self.assertEqual(set(result), {"a", "b"})

    def test_mlb_matches_before_fetching(self):
        source = (ROOT / "providers/mlb/market.py").read_text(encoding="utf-8")
        function = source[source.index("def build_market_lines():"):]
        self.assertLess(
            function.index("matched_events.append("),
            function.index("odds_by_event = fetch_many("),
        )
        self.assertIn("reserved_ids.add(", function)

    def test_sports_run_in_isolated_parallel_processes(self):
        source = (ROOT / "pipeline/full_update.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: node for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        for sport in ("mlb", "nfl", "nba"):
            self.assertIn(f"run_{sport}_update", functions)
        self.assertIn("subprocess.run(", source)
        self.assertIn("ThreadPoolExecutor(max_workers=3)", source)
        self.assertIn("check=False", source)
        self.assertIn("if failures:", source)
        self.assertIn("results = list(executor.map(run_sport, sports))", source)

    def test_nba_parses_in_original_order(self):
        source = (ROOT / "providers/nba/nba_live_markets.py").read_text(encoding="utf-8")
        self.assertIn("for away, home, game, event_id in targets:", source)
        self.assertIn("for book in BOOKS:", source)
        self.assertIn("for directory in (MODEL, WEB):", source)


if __name__ == "__main__":
    unittest.main()
