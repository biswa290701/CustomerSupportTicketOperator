"""Reproducible seed data for the support dashboard.

All customers, companies and incidents below are entirely synthetic.

Seeding uses fixed ticket IDs together with ``INSERT OR IGNORE``, so running
it on every application start is safe: tickets are never duplicated, while any
change already made through the UI (priority, status, draft, ...) is kept.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.database import init_db, upsert_ticket
from app.schemas import Ticket

SEED_TICKETS: list[Ticket] = [
    Ticket(
        id="TCK-1001",
        customer_name="Maya Thornton",
        subject="Duplicate charge on September invoice",
        description=(
            "I was charged twice for the Pro plan on 3 September. My bank shows "
            "two identical authorisations of USD 49.00 one minute apart. Please "
            "confirm whether one of them will be reversed automatically."
        ),
        category="billing",
        priority="high",
        status="open",
        created_at="2026-09-03T09:14:00+00:00",
    ),
    Ticket(
        id="TCK-1002",
        customer_name="Rohan Alvarez",
        subject="Dashboard charts render as blank boxes",
        description=(
            "Since the 2.4.1 release the analytics dashboard shows empty grey "
            "boxes instead of charts. Happens in Chrome and Edge on two "
            "different laptops. Console shows no errors."
        ),
        category="technical",
        priority="high",
        status="in_progress",
        created_at="2026-09-04T13:42:00+00:00",
    ),
    Ticket(
        id="TCK-1003",
        customer_name="Priya Raghunathan",
        subject="Locked out after password reset",
        description=(
            "I reset my password this morning and now the login page loops me "
            "back to the reset form. The reset email arrives fine. I have tried "
            "three browsers with the same result."
        ),
        category="account_access",
        priority="urgent",
        status="open",
        created_at="2026-09-05T07:05:00+00:00",
    ),
    Ticket(
        id="TCK-1004",
        customer_name="Tomas Bergqvist",
        subject="Refund for cancelled annual plan",
        description=(
            "I cancelled the annual plan within the 14 day window on 1 September "
            "and have not received the refund yet. Order reference is "
            "synthetic-order-88231."
        ),
        category="refund",
        priority="medium",
        status="pending",
        created_at="2026-09-05T16:20:00+00:00",
    ),
    Ticket(
        id="TCK-1005",
        customer_name="Alice Fenwick",
        subject="How do I export tickets to CSV?",
        description=(
            "Is there a way to export the ticket list to CSV for our monthly "
            "report? I could not find an export button on the dashboard."
        ),
        category="general",
        priority="low",
        status="open",
        created_at="2026-09-06T10:31:00+00:00",
    ),
    Ticket(
        id="TCK-1006",
        customer_name="Devon Okafor",
        subject="API returns 429 after plan upgrade",
        description=(
            "After upgrading to the Business plan the API started returning 429 "
            "responses within the first minute of usage. Request volume is well "
            "below the documented limit."
        ),
        category="technical",
        priority="urgent",
        status="in_progress",
        created_at="2026-09-07T11:58:00+00:00",
    ),
    Ticket(
        id="TCK-1007",
        customer_name="Hannah Lindqvist",
        subject="Invoice needs company VAT number",
        description=(
            "Could you reissue invoice INV-2026-0457 with our VAT number "
            "SYNTH-VAT-4471 added? Our finance team cannot process it without it."
        ),
        category="billing",
        priority="medium",
        status="pending",
        created_at="2026-09-08T08:47:00+00:00",
    ),
    Ticket(
        id="TCK-1008",
        customer_name="Marcus Delaine",
        subject="Two-factor codes rejected",
        description=(
            "Authenticator codes are rejected with an 'invalid code' message "
            "even though the app clock is synced. Backup codes work, so I can "
            "still sign in."
        ),
        category="account_access",
        priority="medium",
        status="resolved",
        created_at="2026-09-09T14:12:00+00:00",
    ),
    Ticket(
        id="TCK-1009",
        customer_name="Sofia Marchetti",
        subject="Question about seat-based billing",
        description=(
            "We plan to grow from 8 to around 25 seats next quarter. Does seat "
            "billing prorate mid-cycle, or is the change only applied at renewal?"
        ),
        category="general",
        priority="low",
        status="closed",
        created_at="2026-09-10T09:03:00+00:00",
    ),
]


def seed_database(db_path: Path) -> int:
    """Create the schema and insert any missing seed tickets.

    Safe to call on every start: already-present ticket IDs are skipped, so a
    restart never duplicates rows. Returns the number of rows actually added.
    """
    conn = init_db(db_path)
    try:
        return seed_into_connection(conn)
    finally:
        conn.close()


def seed_into_connection(conn: sqlite3.Connection) -> int:
    """Same as :func:`seed_database` but reuses an open connection."""
    added = 0
    for ticket in SEED_TICKETS:
        before = conn.execute(
            "SELECT 1 FROM tickets WHERE id = ?", (ticket.id,)
        ).fetchone()
        upsert_ticket(conn, ticket)
        if before is None:
            added += 1
    return added
