import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_contract import analyze_file, stable_job_id, validate_file, MAX_BYTES

class DataContractTests(unittest.TestCase):
    def setUp(self):
        self.valid = (ROOT / "data/sample_valid.csv").read_bytes()
        self.invalid = (ROOT / "data/sample_invalid.csv").read_bytes()

    def test_sample_known_answers(self):
        checked = validate_file(self.valid, "sample_valid.csv")
        self.assertFalse(checked["errors"])
        report, cleaned = analyze_file(self.valid, "sample_valid.csv")
        self.assertEqual(report["input_rows"], 6)
        self.assertEqual(report["cleaned_rows"], 5)
        self.assertEqual(report["exact_duplicates_removed"], 1)
        self.assertEqual(report["defects"], 3)
        self.assertEqual(report["defect_rate"], 0.6)
        self.assertEqual(len(cleaned), 5)
        self.assertEqual(report["by_machine"]["M03"]["defect_rate"], 1.0)

    def test_missing_column_invalid(self):
        checked = validate_file(self.invalid, "invalid.csv")
        self.assertFalse(checked["schema_valid"])
        self.assertIn("supplier_batch", " ".join(checked["errors"]))

    def test_identical_content_same_job_id(self):
        self.assertEqual(stable_job_id(self.valid), stable_job_id(self.valid))
        modified = self.valid.replace(b"72.1", b"72.2")
        self.assertNotEqual(stable_job_id(self.valid), stable_job_id(modified))

    def test_hard_file_errors(self):
        self.assertTrue(validate_file(b"", "empty.csv")["errors"])
        self.assertTrue(validate_file(self.valid, "test.txt")["errors"])
        self.assertTrue(validate_file(b"\xff" * 200, "binary.csv")["errors"])
        self.assertTrue(validate_file(b"1" * (MAX_BYTES + 1), "large.csv")["errors"])

    def test_soft_quality_flags_not_rejected(self):
        data = self.valid.replace(b"73.0,1", b"999,1")
        check = validate_file(data, "sample.csv")
        self.assertFalse(check["errors"])
        self.assertGreater(check["warning_counts"].get("温度超出演示预警区间（不自动删除）", 0), 0)

    def test_synthetic_6000_schema(self):
        b = (ROOT / "data/manufacturing_6000.csv").read_bytes()
        result = validate_file(b, "manufacturing_6000.csv")
        self.assertFalse(result["errors"])
        self.assertEqual(result["rows"], 6000)
        report, clean = analyze_file(b, "manufacturing_6000.csv")
        self.assertIn("by_shift", report)
        self.assertIn("by_supplier_batch", report)
        self.assertGreater(len(clean), 5900)

if __name__ == "__main__":
    unittest.main()
