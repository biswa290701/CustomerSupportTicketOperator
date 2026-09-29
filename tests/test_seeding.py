"""Tests for database seeding: reproducible and never duplicated."""

from __future__ import annotations

from pathlib import Path

from app import database, seed
from app.schemas import Category, Priority, Status, Ticket

SEED_IDS = [ticket.id for ticket in seed.SEED_TICKETS]


def test_seed_creates_between_8_and_10_tickets(temp_db: Path) -> None:
    seed.seed_database(temp_db)
    conn = database.init_db(temp_db)
    try:
        count = database.count_tickets(conn)
    finally:
        conn.close()
    assert 8 <= count <= 10
    assert count == len(seed.SEED_TICKETS)


def test_seed_data_is_idempotent(temp_db: Path) -> None:
    """Seeding twice (i.e. an application restart) adds no duplicate rows."""
    first = seed.seed_database(temp_db)
    second = seed.seed_database(temp_db)
    third = seed.seed_database(temp_db)

    assert first == len(seed.SEED_TICKETS)
    assert second == 0
    assert third == 0

    conn = database.init_db(temp_db)
    try:
        assert database.count_tickets(conn) == len(seed.SEED_TICKETS)
        ids = [row["id"] for row in conn.execute("SELECT id FROM tickets ORDER BY id")]
    finally:
        conn.close()
    assert sorted(ids) == sorted(set(SEED_IDS))


def test_seeded_tickets_have_valid_vocabulary(temp_db: Path) -> None:
    seed.seed_database(temp_db)
    conn = database.init_db(temp_db)
    try:
        tickets = database.list_tickets(conn)
    finally:
        conn.close()

    assert len(tickets) == len(seed.SEED_TICKETS)
    for ticket in tickets:
        assert isinstance(ticket, Ticket)
        assert isinstance(ticket.category, Category)
        assert isinstance(ticket.priority, Priority)
        assert isinstance(ticket.status, Status)
        assert ticket.created_at.endswith("+00:00")
        assert ticket.customer_name and ticket.subject and ticket.description


def test_seed_covers_the_required_categories(temp_db: Path) -> None:
    seed.seed_database(temp_db)
    conn = database.init_db(temp_db)
    try:
        categories = {t.category.value for t in database.list_tickets(conn)}
    finally:
        conn.close()
    assert categories == {"billing", "technical", "account_access", "refund", "general"}


def test_app_restart_does_not_duplicate_tickets(temp_db: Path, monkeypatch) -> None:
    """Simulates two full application starts against the same database file."""
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("TICKET_DB_PATH", str(temp_db))

    with TestClient(app) as first_start:  # first application start
        assert first_start.get("/").status_code == 200
    with TestClient(app) as second_start:  # restart
        assert second_start.get("/").status_code == 200

    conn = database.init_db(temp_db)
    try:
        count = database.count_tickets(conn)
    finally:
        conn.close()
    assert count == len(seed.SEED_TICKETS)


def test_seed_preserves_operator_changes_on_restart(temp_db: Path) -> None:
    """A restart must not reset a ticket that the operator already edited."""
    seed.seed_database(temp_db)
    conn = database.init_db(temp_db)
    try:
        database.update_ticket_fields(conn, "TCK-1001", priority=Priority.URGENT)
        seed.seed_into_connection(conn)  # what the app does on start
        ticket = database.get_ticket(conn, "TCK-1001")
    finally:
        conn.close()

    assert ticket is not None
    assert ticket.priority == Priority.URGENT
