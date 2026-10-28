import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location("app_data_refresh_module", os.path.join(ROOT, "app.py"))
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)


class AskAIDataRefreshTests(unittest.TestCase):
    def setUp(self):
        self.data_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.data_directory.cleanup)
        self.data_dir_patch = patch.object(app_module, "DATA_DIR", self.data_directory.name)
        self.data_dir_patch.start()
        self.addCleanup(self.data_dir_patch.stop)
        self.sectors_patch = patch.object(app_module, "SECTORS", {"IT": ["INFY.NS"]})
        self.sectors_patch.start()
        self.addCleanup(self.sectors_patch.stop)
        self.analytics_patch = patch.object(app_module, "ANALYTICS_SECTORS", ["IT"])
        self.analytics_patch.start()
        self.addCleanup(self.analytics_patch.stop)
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1

    @staticmethod
    def downloaded_data(closes, dates):
        columns = pd.MultiIndex.from_tuples([("Close", "INFY.NS")])
        return pd.DataFrame(
            closes,
            index=pd.DatetimeIndex(pd.to_datetime(dates), name="Date"),
            columns=columns,
        )

    def test_refreshed_download_is_used_in_next_ask_ai_context(self):
        downloads = [
            self.downloaded_data(
                [80, 90, 100],
                ["2025-01-01", "2025-01-02", "2025-01-03"],
            ),
            self.downloaded_data(
                [100, 110, 125],
                ["2026-03-01", "2026-03-02", "2026-03-03"],
            ),
        ]
        with patch.object(app_module.yf, "download", side_effect=downloads):
            for expected_price in (100, 125):
                response = self.client.post(
                    "/update_data",
                    json={"start_date": "2025-01-01"},
                )
                self.assertEqual(response.status_code, 200)

                metrics = app_module.get_core_stock_metrics()
                self.assertEqual(metrics[0]["latest_close"], expected_price)

            messages = app_module._build_chat_messages(
                "What is the latest price for INFY?",
                metrics,
                [],
            )

        system_prompt = messages[0]["content"]
        self.assertIn('"latest_close_from_dataset": 125.0', system_prompt)
        self.assertIn('"data_as_of": "2026-03-03"', system_prompt)
        self.assertIn("Current Market Mind stock-data snapshot", system_prompt)
        self.assertIn("current data snapshot below is the source of truth", system_prompt)

    def test_failed_download_does_not_replace_existing_stock_data(self):
        data_path = app_module._stock_data_path("IT", "INFY.NS")
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        pd.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Close": [90, 100],
        }).to_csv(data_path, index=False)
        with patch.object(app_module.yf, "download", return_value=pd.DataFrame()):
            response = self.client.post(
                "/update_data",
                json={"start_date": "2025-01-01"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(app_module.get_core_stock_metrics()[0]["latest_close"], 100)
        self.assertIn("Existing data has been kept", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
