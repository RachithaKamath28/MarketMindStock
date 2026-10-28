import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location("app_module", os.path.join(ROOT, "app.py"))
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)


class InvestmentRecommendationTests(unittest.TestCase):
    def test_all_sectors_used_when_none_selected(self):
        result = app_module.analyze_investment_recommendations(budget=None, selected_sectors=None, risk_preference="Medium")
        self.assertEqual(result["selected_sectors"], ["IT", "Banking", "Pharma", "FMCG"])
        self.assertGreaterEqual(len(result["recommendations"]), 1)

    def test_selected_sector_filters_recommendations(self):
        result = app_module.analyze_investment_recommendations(budget=100000, selected_sectors=["IT"], risk_preference="Low")
        self.assertEqual(result["selected_sectors"], ["IT"])
        self.assertTrue(all(item["sector"] == "IT" for item in result["recommendations"]))
        self.assertEqual(result["portfolio_summary"]["budget"], 100000)


class AIAdvisorSectorSelectionTests(unittest.TestCase):
    """Covers the new Sector Selection dropdown behaviour on the AI
    Investment Advisor (/api/ai-advisor -> analyze_ai_advisor)."""

    def test_no_sector_auto_picks_best_across_all(self):
        result = app_module.analyze_ai_advisor(budget=100000, risk_preference="Medium")
        self.assertNotIn("error", result)
        self.assertIsNone(result["selected_sector"])
        self.assertFalse(result["sector_locked"])
        self.assertIn(result["best_sector"], app_module.ANALYTICS_SECTORS)

    def test_explicit_sector_restricts_recommendations_to_that_sector(self):
        result = app_module.analyze_ai_advisor(budget=100000, risk_preference="Medium", sector="IT")
        self.assertNotIn("error", result)
        self.assertEqual(result["best_sector"], "IT")
        self.assertEqual(result["selected_sector"], "IT")
        self.assertTrue(result["sector_locked"])
        self.assertTrue(all(item["sector"] == "IT" for item in result["recommendations"]))
        # The sector-comparison table should also be scoped to just IT.
        self.assertTrue(all(s["sector"] == "IT" for s in result["sector_comparison"]))

    def test_budget_sizing_and_substitution_stay_within_selected_sector(self):
        result = app_module.analyze_ai_advisor(budget=5000, risk_preference="Medium", sector="Banking")
        self.assertNotIn("error", result)
        for pick in result["recommendations"]:
            self.assertEqual(pick["sector"], "Banking")
            if pick["shares"] is not None:
                self.assertGreaterEqual(pick["shares"], 0)

    def test_invalid_sector_returns_error(self):
        result = app_module.analyze_ai_advisor(budget=100000, sector="NotASector")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
