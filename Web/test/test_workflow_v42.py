"""Regression checks for the live AWS job workflow. No AWS calls made."""
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import aws_client
from aws_client import CloudAPI, CloudAPIError
from data_contract import stable_job_id

DATA = b"timestamp,machine_id,shift,product_id,supplier_batch,temperature,defect_label\n2026-09-01T08:00:00,M01,Day,P01,SB-100,75.1,0\n"


class FakeResponse:
    def __init__(self, status_code=200, data=None, xml=""):
        self.status_code = status_code
        self.ok = status_code < 400
        self.payload = data or {}
        self.text = xml
        self.headers = {}
    def json(self):
        return self.payload


def test_duplicate_completed_no_new_s3_put(monkeypatch):
    calls = []
    job_id = stable_job_id(DATA)
    def request(method, url, **kwargs):
        calls.append(method)
        assert method == "GET"
        return FakeResponse(data={"job_id": job_id, "status": "COMPLETED"})
    monkeypatch.setattr(aws_client.requests, "request", request)
    info = CloudAPI("https://api.example", "secret").upload("a.csv", DATA)
    assert info["duplicate"] and info["job_id"] == job_id
    assert calls == ["GET"]


def test_valid_new_job_preflights_then_uploads(monkeypatch):
    calls = []
    job_id = stable_job_id(DATA)
    def request(method, url, **kwargs):
        calls.append(method)
        if method == "GET":
            return FakeResponse(status_code=404)
        if method == "POST":
            return FakeResponse(data={"job_id": job_id, "upload_url": "https://s3.example/put", "upload_headers": {"Content-Type": "text/csv"}})
        return FakeResponse()
    monkeypatch.setattr(aws_client.requests, "request", request)
    info = CloudAPI("https://api.example", "secret").upload("a.csv", DATA)
    assert info["job_id"] == job_id
    assert calls == ["GET", "POST", "PUT"]


def test_invalid_schema_still_sent_to_aws(monkeypatch):
    data = b"timestamp,machine_id\n2026-09-01T08:00:00,M01\n"
    job_id = stable_job_id(data)
    calls = []
    def request(method, url, **kwargs):
        calls.append(method)
        if method == "GET":
            return FakeResponse(status_code=404)
        if method == "POST":
            return FakeResponse(data={"job_id": job_id, "upload_url": "https://s3.example/put", "upload_headers": {"Content-Type": "text/csv"}})
        return FakeResponse()
    monkeypatch.setattr(aws_client.requests, "request", request)
    CloudAPI("https://api.example", "secret").upload("invalid.csv", data)
    assert calls == ["GET", "POST", "PUT"]


def test_error_does_not_leak_signed_s3_url(monkeypatch):
    job_id = stable_job_id(DATA)
    def request(method, url, **kwargs):
        if method == "GET":
            return FakeResponse(status_code=404)
        if method == "POST":
            return FakeResponse(data={"job_id": job_id, "upload_url": "https://s3.example/?X-Amz-Signature=secret-sig", "upload_headers": {"Content-Type": "text/csv"}})
        return FakeResponse(status_code=403, xml="<Error><Code>AccessDenied</Code></Error>")
    monkeypatch.setattr(aws_client.requests, "request", request)
    with pytest.raises(CloudAPIError) as failure:
        CloudAPI("https://api.example", "secret").upload("a.csv", DATA)
    assert failure.value.code == "AccessDenied"
    assert "secret-sig" not in str(failure.value)
