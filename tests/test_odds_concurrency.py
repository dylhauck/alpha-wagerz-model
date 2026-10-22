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

    def test_bounded_concurrent_fetchers(self):
        for relative in (
            "providers/mlb/market.py",
            "providers/nfl/nfl_odds.py",
            "providers/nba/nba_live_markets.py",
        ):
            with self.subTest(relative=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                tree = ast.parse(source)
                calls = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "ThreadPoolExecutor"
                ]
                self.assertEqual(len(calls), 1)
                self.assertTrue(
                    any(keyword.arg == "max_workers" for keyword in calls[0].keywords)
                )
                self.assertIn("pool.map(", source)

    def test_mlb_matches_before_fetching(self):
        source = (ROOT / "providers/mlb/market.py").read_text(encoding="utf-8")
        function = source[source.index("def build_market_lines():"):]
        self.assertLess(
            function.index("matched_events.append("),
            function.index("odds_results = list(pool.map("),
        )
        self.assertIn("reserved_ids.add(", function)

    def test_nba_parses_in_original_order(self):
        source = (ROOT / "providers/nba/nba_live_markets.py").read_text(encoding="utf-8")
        self.assertIn("for target, data, error in results:", source)
        self.assertIn("for book in BOOKS:", source)
        self.assertIn("for directory in (MODEL, WEB):", source)


if __name__ == "__main__":
    unittest.main()
