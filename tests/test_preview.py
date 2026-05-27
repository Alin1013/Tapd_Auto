import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tapd_auto.preview import build_local_report_url


class PreviewTests(unittest.TestCase):
    def test_build_local_report_url_points_to_report_index(self):
        self.assertEqual(
            build_local_report_url("2026-05-26", port=8765),
            "http://127.0.0.1:8765/public/reports/2026-05-26/index.html",
        )


if __name__ == "__main__":
    unittest.main()
