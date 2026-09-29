"""Browser-operator tests.

These tests start a real uvicorn server and drive a real Chromium instance
through the dashboard UI. Install the browser first:

    python -m playwright install chromium

Skip them with:  pytest -m "not operator"
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.operator

DRAFT_TEXT = (
    "Hello, thank you for reporting this. Our team is reviewing the details "
    "and will follow up within one business day."
)


def _log_records(operator) -> list[dict]:
    path = operator.logger.jsonl_path
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_operator_launches_and_finds_ticket(operator) -> None:
    operator.open_dashboard()

    assert operator.locate_ticket("TCK-1003") is True
    # Unknown ids are reported as missing instead of raising.
    assert operator.locate_ticket("TCK-9999") is False

    records = _log_records(operator)
    assert any(r["action"] == "locate_ticket" and r["result"] == "found" for r in records)
    assert any(r["action"] == "locate_ticket" and r["result"] == "not_found" for r in records)
    assert any("ticket=TCK-1003" in line for line in operator.logger.log_path.read_text("utf-8").splitlines())


def test_operator_inspects_ticket_state(operator) -> None:
    state = operator.inspect_ticket("TCK-1006")
    assert state.found is True
    assert state.category == "technical"
    assert state.priority == "urgent"
    assert state.status == "in_progress"
    assert state.customer_name == "Devon Okafor"

    missing = operator.inspect_ticket("TCK-9999")
    assert missing.found is False


def test_operator_changes_priority_and_verifies_via_ui(operator) -> None:
    before = operator.inspect_ticket("TCK-1002")
    assert before.found is True
    target = next(p for p in ("low", "medium", "high", "urgent") if p != before.priority)

    result = operator.update_ticket("TCK-1002", priority=target)
    assert result.result == "updated", result.detail
    assert result.changes == {"priority": target}

    after = operator.inspect_ticket("TCK-1002")
    assert after.priority == target
    assert after.status == before.status  # untouched fields stay untouched
    assert after.category == before.category

    # Screenshot captured and the change recorded in the action log.
    assert Path(result.screenshot).exists()
    records = _log_records(operator)
    update_records = [r for r in records if r["action"] == "update_ticket"]
    assert update_records[-1]["result"] == "updated"
    assert f"priority: {before.priority} -> {target}" in update_records[-1]["detail"]


def test_operator_skips_unchanged_update(operator) -> None:
    current = operator.inspect_ticket("TCK-1001")
    result = operator.update_ticket("TCK-1001", priority=current.priority)
    assert result.result == "skipped"

    # No write was performed: the state is still the original one.
    assert operator.inspect_ticket("TCK-1001").priority == current.priority


def test_operator_updates_status_through_ui(operator) -> None:
    result = operator.update_ticket("TCK-1005", status="in_progress")
    assert result.result == "updated", result.detail
    assert operator.inspect_ticket("TCK-1005").status == "in_progress"


def test_operator_saves_draft_response(operator) -> None:
    result = operator.save_draft_response("TCK-1004", DRAFT_TEXT)
    assert result.result == "updated", result.detail

    state = operator.inspect_ticket("TCK-1004")
    assert state.draft_response == DRAFT_TEXT

    # Saving the identical text again must not repeat the write.
    repeat = operator.save_draft_response("TCK-1004", DRAFT_TEXT)
    assert repeat.result == "skipped"

    # The draft is also announced on the list page.
    assert operator.locate_ticket("TCK-1004")
    assert "yes" in operator.page.locator(
        "[data-testid='ticket-cell-draft-TCK-1004']"
    ).inner_text()


def test_operator_rejects_invalid_value(operator) -> None:
    with pytest.raises(ValueError):
        operator.update_ticket("TCK-1001", priority="catastrophic")


def test_operator_writes_screenshots_and_logs(operator) -> None:
    operator.open_dashboard()
    operator.locate_ticket("TCK-1007")

    shots = sorted(Path(operator.screenshot_dir).glob("*.png"))
    assert len(shots) >= 2
    assert operator.logger.log_path.exists()
    records = _log_records(operator)
    assert len(records) >= 3
    for record in records:
        assert set(record) >= {"timestamp", "ticket_id", "action", "result"}
        assert record["timestamp"]
