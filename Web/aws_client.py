"""Streamlit -> AWS API Gateway adapter with SAFE, actionable errors.

Presigned S3 URLs are bearer credentials. NEVER put signed URLs or temporary
AWS session tokens in UI errors, logs, or exception strings.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET

import requests
from data_contract import MAX_BYTES, VERSION, stable_job_id


class CloudAPIError(RuntimeError):
    """Safe structured error: contains no request URL, query or security token."""

    def __init__(self, stage: str, status_code: int | None, code: str,
                 *, request_id: str = "", reason: str = "") -> None:
        self.stage = stage
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.reason = reason
        info = f"{stage} · HTTP {status_code} · {code}" if status_code else f"{stage} · {code}"
        if reason:
            info += f" · {reason}"
        if request_id:
            info += f" · Request ID: {request_id}"
        super().__init__(info)


def _xml_value(payload: str, name: str) -> str:
    """Read the S3 XML error fields; return only short, non-sensitive text."""
    if not payload or len(payload) > 65536:
        return ""
    try:
        root = ET.fromstring(payload)
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] == name:
                return (node.text or "")[:1024].strip()
    except ET.ParseError:
        return ""
    return ""


def _error_response(response: requests.Response, stage: str) -> CloudAPIError:
    code = _xml_value(response.text, "Code") or f"HTTP_{response.status_code}"
    # Only permit short AWS error identifiers, never raw untrusted error data.
    if not code.isascii() or not code.replace("_", "").isalnum() or len(code) > 45:
        code = f"HTTP_{response.status_code}"
    message = _xml_value(response.text, "Message").lower()
    reason = "URL_EXPIRED" if "request has expired" in message else ""
    request_id = response.headers.get("x-amz-request-id", "")
    if not request_id.isascii() or len(request_id) > 96 or not request_id.replace("-", "").isalnum():
        request_id = ""
    return CloudAPIError(stage, response.status_code, code,
                         request_id=request_id, reason=reason)


def _safe_request(method: str, url: str, stage: str, **kwargs) -> requests.Response:
    """Never expose requests' exception string: it can contain a signed URL."""
    try:
        result = requests.request(method, url, **kwargs)
    except requests.Timeout:
        raise CloudAPIError(stage, None, "NETWORK_TIMEOUT") from None
    except requests.RequestException:
        raise CloudAPIError(stage, None, "NETWORK_ERROR") from None
    return result


class CloudAPI:
    def __init__(self, base_url: str, demo_key: str):
        if not base_url.startswith("https://"):
            raise ValueError("AWS_API_BASE_URL must use https://")
        if not demo_key:
            raise ValueError("Missing DEMO_API_KEY in Streamlit Secrets")
        self.base_url = base_url.rstrip("/")
        self.headers = {"x-demo-key": demo_key}

    @staticmethod
    def _json(response: requests.Response, stage: str) -> dict:
        if not response.ok:
            raise _error_response(response, stage)
        try:
            data = response.json()
        except ValueError:
            raise CloudAPIError(stage, response.status_code, "INVALID_JSON") from None
        if not isinstance(data, dict):
            raise CloudAPIError(stage, response.status_code, "INVALID_JSON_OBJECT")
        return data

    def upload(self, file_name: str, data: bytes) -> dict:
        if len(data) > MAX_BYTES:
            raise ValueError("File exceeds 10 MiB limit")
        payload = {
            "filename": file_name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "processing_version": VERSION,
        }
        # Exact bytes + v1 identify the job. Query DynamoDB through the existing
        # API before requesting a new S3 upload URL. The AWS validation Lambda
        # still independently checks the contents on first submission.
        job_id = stable_job_id(data)
        existing = self.status(job_id)
        if existing.get("status") != "AWAITING_EVENT":
            return {
                "job_id": job_id,
                "duplicate": True,
                "existing": existing,
                "existing_status": existing.get("status", "UNKNOWN"),
            }
        response = _safe_request("POST", f"{self.base_url}/uploads", "API_UPLOAD_URL",
                                 json=payload, headers=self.headers, timeout=20)
        info = self._json(response, "API_UPLOAD_URL")
        if info.get("job_id") != stable_job_id(data):
            raise CloudAPIError("API_UPLOAD_URL", 200, "JOB_ID_MISMATCH")
        url = info.get("upload_url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise CloudAPIError("API_UPLOAD_URL", 200, "INVALID_UPLOAD_URL")
        # Content-Type must match the ContentType value signed by Web API Lambda.
        response = _safe_request("PUT", url, "S3_UPLOAD", data=data,
                                 headers=info.get("upload_headers", {"Content-Type": "text/csv"}),
                                 timeout=75)
        if not response.ok:
            raise _error_response(response, "S3_UPLOAD")
        return info

    def status(self, job_id: str) -> dict:
        response = _safe_request("GET", f"{self.base_url}/jobs/{job_id}", "API_JOB_STATUS",
                                 headers=self.headers, timeout=20)
        if response.status_code == 404:
            return {"job_id": job_id, "status": "AWAITING_EVENT"}
        return self._json(response, "API_JOB_STATUS")

    def fetch_json(self, url: str) -> dict:
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Invalid report download address")
        response = _safe_request("GET", url, "S3_REPORT_DOWNLOAD", timeout=30)
        return self._json(response, "S3_REPORT_DOWNLOAD")

    def fetch_bytes(self, url: str) -> bytes:
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Invalid download address")
        response = _safe_request("GET", url, "S3_CSV_DOWNLOAD", timeout=45)
        if not response.ok:
            raise _error_response(response, "S3_CSV_DOWNLOAD")
        if len(response.content) > MAX_BYTES:
            raise ValueError("Downloaded data exceeds 10 MiB")
        return response.content
