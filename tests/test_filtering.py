"""Tests for the ticket list, its filters and the detail page."""

from __future__ import annotations

# Expected values derived from app.seed.SEED_TICKETS
OPEN = ["TCK-1001", "TCK-1003", "TCK-1005"]
REFUND = ["TCK-1004"]
URGENT = ["TCK-1003", "TCK-1006"]
BILLING = ["TCK-1001", "TCK-1007"]


def _row_ids(html: str) -> list[str]:
    import re

    return sorted(set(re.findall(r"ticket-row-(TCK-\d+)", html)))


def test_list_shows_all_seeded_tickets(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'data-testid="ticket-list"' in response.text
    assert len(_row_ids(response.text)) == 9


def test_filter_by_status(client) -> None:
    response = client.get("/", params={"status": "open"})
    assert response.status_code == 200
    assert _row_ids(response.text) == sorted(OPEN)
    assert "3 of 9 tickets shown" in response.text


def test_filter_by_category(client) -> None:
    response = client.get("/", params={"category": "refund"})
    assert _row_ids(response.text) == sorted(REFUND)


def test_filter_by_priority(client) -> None:
    response = client.get("/", params={"priority": "urgent"})
    assert _row_ids(response.text) == sorted(URGENT)


def test_combined_filters(client) -> None:
    response = client.get("/", params={"category": "billing", "priority": "high"})
    assert _row_ids(response.text) == ["TCK-1001"]

    response = client.get(
        "/", params={"category": "billing", "priority": "urgent"}
    )
    assert _row_ids(response.text) == []
    assert 'data-testid="empty-list"' in response.text


def test_invalid_filter_value_is_rejected(client) -> None:
    response = client.get("/", params={"status": "not-a-status"})
    assert response.status_code == 422


def test_detail_page_renders_ticket_fields(client) -> None:
    response = client.get("/tickets/TCK-1003")
    assert response.status_code == 200
    assert 'data-testid="ticket-id">TCK-1003<' in response.text
    assert 'data-testid="ticket-priority">urgent<' in response.text
    assert 'data-testid="ticket-status">open<' in response.text
    assert 'data-testid="select-priority"' in response.text
    assert 'data-testid="save-triage"' in response.text
    assert 'data-testid="save-draft"' in response.text


def test_unknown_ticket_returns_404(client) -> None:
    assert client.get("/tickets/TCK-9999").status_code == 404


def test_triage_form_updates_priority_and_status(client) -> None:
    response = client.post(
        "/tickets/TCK-1001/triage",
        data={"category": "billing", "priority": "low", "status": "in_progress"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/tickets/TCK-1001?saved=triage"

    detail = client.get(response.headers["location"])
    assert 'data-testid="ticket-priority">low<' in detail.text
    assert 'data-testid="ticket-status">in_progress<' in detail.text
    assert 'data-testid="flash-message"' in detail.text

    # The change is visible in the filtered list as well.
    filtered = client.get("/", params={"priority": "low"})
    assert "TCK-1001" in _row_ids(filtered.text)


def test_draft_form_saves_response(client) -> None:
    text = "Hi Maya, we spotted the duplicate charge and issued a reversal."
    response = client.post(
        "/tickets/TCK-1001/draft",
        data={"draft_response": text},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = client.get("/tickets/TCK-1001")
    assert text in detail.text
    assert 'data-testid="ticket-draft">' + text + "</p>" in detail.text
