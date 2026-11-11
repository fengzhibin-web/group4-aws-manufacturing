import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aws import api_lambda as a

class FakeS3:
    def generate_presigned_url(self, method, Params=None, **kwargs):
        return f"https://example-bucket.s3.amazonaws.com/{Params['Key']}?signed=yes"

class FakeTable:
    def get_item(self, **kwargs):
        return {"Item": {"status": "COMPLETED", "report_key": "reports/abc123/report.json",
                         "cleaned_key": "cleaned/abc123/cleaned.csv", "updated_at": "2026-11-10T10:00:00"}}

class FakeDB:
    def Table(self, name):
        return FakeTable()

class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.saved = (a.BUCKET, a.TABLE, a.DEMO_KEY, a.s3, a.db)
        a.BUCKET = "test-bucket"
        a.TABLE = "test-table"
        a.DEMO_KEY = "good-secret"
        a.s3 = FakeS3()
        a.db = FakeDB()

    def tearDown(self):
        a.BUCKET, a.TABLE, a.DEMO_KEY, a.s3, a.db = self.saved

    def event(self, method, path, body=None, key="good-secret"):
        return {"headers": {"x-demo-key": key},
                "requestContext": {"http": {"method": method}},
                "rawPath": path, "body": json.dumps(body) if body else ""}

    def test_unauthorized(self):
        self.assertEqual(a.lambda_handler(self.event("GET", "/jobs/0123456789abcdef", key="bad"), None)["statusCode"], 401)

    def test_presign_creates_raw_prefix(self):
        body = {"filename": "factory.csv", "sha256": "a" * 64, "size_bytes": 10, "processing_version": "v1"}
        resp = a.lambda_handler(self.event("POST", "/uploads", body), None)
        self.assertEqual(resp["statusCode"], 200)
        output = json.loads(resp["body"])
        self.assertTrue(output["key"].startswith("raw/uploads/"))
        self.assertEqual(output["upload_headers"], {"Content-Type": "text/csv"})

    def test_status_with_signed_outputs(self):
        resp = a.lambda_handler(self.event("GET", "/jobs/0123456789abcdef"), None)
        self.assertEqual(resp["statusCode"], 200)
        output = json.loads(resp["body"])
        self.assertEqual(output["status"], "COMPLETED")
        self.assertIn("report_url", output)
        self.assertIn("cleaned_url", output)

if __name__ == "__main__":
    unittest.main()
