"""SQLite persistence layer.

Only the web application touches this module. The browser operator never
imports it - it works exclusively through the UI.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.schemas import Category, Priority, Status, Ticket, TicketFilters

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
    id              TEXT PRIMARY KEY,
    customer_name   TEXT NOT NULL,
    subject         TEXT NOT NULL,
    description     TEXT NOT NULL,
    category        TEXT NOT NULL,
    priority        TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    draft_response  TEXT
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (and create if needed) the ticket database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create the schema if it does not exist and return a connection."""
    conn = connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def _row_to_ticket(row: sqlite3.Row) -> Ticket:
    return Ticket(
        id=row["id"],
        customer_name=row["customer_name"],
        subject=row["subject"],
        description=row["description"],
        category=Category(row["category"]),
        priority=Priority(row["priority"]),
        status=Status(row["status"]),
        created_at=row["created_at"],
        draft_response=row["draft_response"],
    )


def list_tickets(conn: sqlite3.Connection, filters: TicketFilters | None = None) -> list[Ticket]:
    """Return tickets, optionally filtered by status / category / priority."""
    query = "SELECT * FROM tickets"
    clauses: list[str] = []
    values: list[str] = []

    if filters is not None:
        if filters.status is not None:
            clauses.append("status = ?")
            values.append(filters.status.value)
        if filters.category is not None:
            clauses.append("category = ?")
            values.append(filters.category.value)
        if filters.priority is not None:
            clauses.append("priority = ?")
            values.append(filters.priority.value)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC, id ASC"

    rows = conn.execute(query, values).fetchall()
    return [_row_to_ticket(row) for row in rows]


def get_ticket(conn: sqlite3.Connection, ticket_id: str) -> Ticket | None:
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return _row_to_ticket(row) if row else None


def upsert_ticket(conn: sqlite3.Connection, ticket: Ticket) -> None:
    """Insert a ticket. Existing rows are left untouched (idempotent seeding)."""
    conn.execute(
        """
        INSERT OR IGNORE INTO tickets
            (id, customer_name, subject, description, category, priority,
             status, created_at, draft_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticket.id,
            ticket.customer_name,
            ticket.subject,
            ticket.description,
            ticket.category.value,
            ticket.priority.value,
            ticket.status.value,
            ticket.created_at,
            ticket.draft_response,
        ),
    )
    conn.commit()


def update_ticket_fields(
    conn: sqlite3.Connection,
    ticket_id: str,
    *,
    category: Category | None = None,
    priority: Priority | None = None,
    status: Status | None = None,
) -> bool:
    """Update the triage fields of a ticket. Returns True when a row changed."""
    assignments: list[str] = []
    values: list[str] = []
    if category is not None:
        assignments.append("category = ?")
        values.append(category.value)
    if priority is not None:
        assignments.append("priority = ?")
        values.append(priority.value)
    if status is not None:
        assignments.append("status = ?")
        values.append(status.value)
    if not assignments:
        return False

    values.append(ticket_id)
    cursor = conn.execute(
        f"UPDATE tickets SET {', '.join(assignments)} WHERE id = ?", values
    )
    conn.commit()
    return cursor.rowcount > 0


def save_draft_response(conn: sqlite3.Connection, ticket_id: str, text: str) -> bool:
    """Store a draft response for a ticket."""
    cursor = conn.execute(
        "UPDATE tickets SET draft_response = ? WHERE id = ?",
        (text, ticket_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def count_tickets(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()
    return int(row["n"])
