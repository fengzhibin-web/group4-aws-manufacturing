"""Streamlit session regression: language/mode changes preserve current AWS job."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_language_toggle_keeps_mode_and_job_id():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.radio[0].value == "en"
    at.radio[1].set_value("aws").run()
    assert not at.exception, [e.message for e in at.exception]
    at.session_state["aws_job_id"] = "0123456789abcdef"
    at.radio[0].set_value("zh").run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.radio[1].value == "aws"
    assert at.session_state["aws_job_id"] == "0123456789abcdef"
    at.radio[0].set_value("en").run()
    assert at.radio[1].value == "aws"
    at.radio[1].set_value("local").run()
    assert at.session_state["aws_job_id"] == "0123456789abcdef"
    at.radio[1].set_value("aws").run()
    assert at.session_state["aws_job_id"] == "0123456789abcdef"


def test_url_restores_job_after_page_reload():
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["job"] = "0123456789abcdef"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.session_state["aws_job_id"] == "0123456789abcdef"
    assert at.session_state["execution_mode"] == "aws"


def test_aws_status_is_polled_without_clicking_refresh(monkeypatch):
    from aws_client import CloudAPI
    calls = []
    job_id = "0123456789abcdef"
    def fake_status(self, key):
        calls.append(key)
        return {"job_id": key, "status": "QUEUED"}
    monkeypatch.setattr(CloudAPI, "status", fake_status)
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["AWS_API_BASE_URL"] = "https://api.example"
    at.secrets["DEMO_API_KEY"] = "unit-test-only-not-real"
    at.query_params["job"] = job_id
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert calls == [job_id]
    assert at.session_state["aws_status"]["status"] == "QUEUED"
    assert at.session_state["aws_polling"] is True


def test_duplicate_notice_survives_language_changes():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.session_state["execution_mode"] = "aws"
    at.session_state["aws_job_id"] = "0123456789abcdef"
    at.session_state["aws_notice"] = {
        "type": "duplicate",
        "job_id": "0123456789abcdef",
        "status": "COMPLETED",
    }
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("Duplicate content detected" in w.message for w in at.warning)
    assert "本地演示" not in str(at.radio[1].options)
    at.radio[0].set_value("zh").run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("检测到相同内容" in w.message for w in at.warning)
    assert "AWS云端模式" in str(at.radio[1].options)
    at.radio[0].set_value("en").run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("Duplicate content detected" in w.message for w in at.warning)
    assert at.session_state["aws_notice"]["job_id"] == "0123456789abcdef"
