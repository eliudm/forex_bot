import unittest
import pandas as pd

from ai_engine.enhanced_engine import EnhancedAIEngine


class EnhancedEngineTests(unittest.TestCase):
    def test_predict_handles_raw_ohlc_data_without_precomputed_indicators(self):
        engine = EnhancedAIEngine("EURUSD")
        df = pd.DataFrame(
            [
                {"time": "2024-01-01 00:00:00", "open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005, "volume": 100},
                {"time": "2024-01-01 01:00:00", "open": 1.1005, "high": 1.1020, "low": 1.1000, "close": 1.1015, "volume": 110},
                {"time": "2024-01-01 02:00:00", "open": 1.1015, "high": 1.1030, "low": 1.1010, "close": 1.1020, "volume": 120},
            ]
        )

        result = engine.predict(df, min_confidence=0.55)

        self.assertIn("action", result)
        self.assertIn("confidence", result)
        self.assertEqual(result["action"], "WAIT")


if __name__ == "__main__":
    unittest.main()
