"""Credential-free Streamlit -> AWS API Gateway adapter.
Never copy AWS Academy temporary access keys into a public application.
"""
from __future__ import annotations

import hashlib
import requests
from data_contract import MAX_BYTES, VERSION, stable_job_id


class CloudAPI:
    def __init__(self, base_url: str, demo_key: str):
        if not base_url.startswith("https://"):
            raise ValueError("AWS_API_BASE_URL 必须使用 https://")
        if not demo_key:
            raise ValueError("缺少 DEMO_API_KEY；请先在Streamlit secrets设置")
        self.base_url = base_url.rstrip("/")
        self.headers = {"x-demo-key": demo_key}

    def _json(self, response: requests.Response) -> dict:
        response.raise_for_status()
        content = response.json()
        if not isinstance(content, dict):
            raise ValueError("API返回格式不是JSON对象")
        return content

    def upload(self, file_name: str, data: bytes) -> dict:
        if len(data) > MAX_BYTES:
            raise ValueError("文件超过10 MiB")
        payload = {
            "filename": file_name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "processing_version": VERSION,
        }
        r = requests.post(f"{self.base_url}/uploads", json=payload, headers=self.headers, timeout=20)
        info = self._json(r)
        if info.get("job_id") != stable_job_id(data):
            raise ValueError("API返回的Job ID与本地计算不一致")
        url = info["upload_url"]
        if not url.startswith("https://"):
            raise ValueError("预签名上传地址不是HTTPS")
        response = requests.put(url, data=data, headers=info.get("upload_headers", {"Content-Type": "text/csv"}), timeout=75)
        response.raise_for_status()
        return info

    def status(self, job_id: str) -> dict:
        r = requests.get(f"{self.base_url}/jobs/{job_id}", headers=self.headers, timeout=20)
        if r.status_code == 404:
            return {"job_id": job_id, "status": "AWAITING_EVENT"}
        return self._json(r)

    def fetch_json(self, url: str) -> dict:
        if not url.startswith("https://"):
            raise ValueError("无效的下载地址")
        r = requests.get(url, timeout=30)
        return self._json(r)

    def fetch_bytes(self, url: str) -> bytes:
        if not url.startswith("https://"):
            raise ValueError("无效的下载地址")
        r = requests.get(url, timeout=45)
        r.raise_for_status()
        if len(r.content) > MAX_BYTES:
            raise ValueError("下载结果超出客户端大小限制")
        return r.content
