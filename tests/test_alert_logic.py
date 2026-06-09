"""Run with: python -m pytest tests/  (or python tests/test_alert_logic.py)"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from alert_logic import categorize, has_alerts  # noqa: E402

TODAY = date(2026, 6, 9)
TZ = "America/Edmonton"


def _docs():
    return [
        {"file_name": "A", "expiry_raw": "2026-07-09T06:00:00Z"},  # +30
        {"file_name": "B", "expiry_raw": "2026-06-16T06:00:00Z"},  # +7
        {"file_name": "C", "expiry_raw": "2026-06-08T06:00:00Z"},  # expired
        {"file_name": "D", "expiry_raw": "2026-06-09T06:00:00Z"},  # today
        {"file_name": "E", "expiry_raw": "2026-06-20T06:00:00Z"},  # +11 no alert
    ]


def test_buckets():
    b = categorize(_docs(), TZ, [30, 7], today=TODAY)
    assert [d["file_name"] for d in b["warn"][30]] == ["A"]
    assert [d["file_name"] for d in b["warn"][7]] == ["B"]
    assert {d["file_name"] for d in b["expired"]} == {"C", "D"}
    assert has_alerts(b)


def test_no_alert():
    b = categorize([{"file_name": "E", "expiry_raw": "2026-06-20T06:00:00Z"}], TZ, [30, 7], today=TODAY)
    assert not has_alerts(b)


if __name__ == "__main__":
    test_buckets()
    test_no_alert()
    print("ok")
