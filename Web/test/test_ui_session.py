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
