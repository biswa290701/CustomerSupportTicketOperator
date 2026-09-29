"""FastAPI web application for the customer support dashboard.

Run with:  python -m app.main
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config, database, seed
from app.schemas import Category, Priority, Status, TicketFilters

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_APP_STATE: dict[str, object] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the database and seed it exactly once per process start."""
    db_path = config.get_db_path()
    conn = database.init_db(db_path)
    seed.seed_into_connection(conn)
    _APP_STATE["conn"] = conn
    _APP_STATE["db_path"] = db_path
    try:
        yield
    finally:
        conn.close()
        _APP_STATE.pop("conn", None)


app = FastAPI(title="Customer Support Ticket Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _conn():
    return _APP_STATE["conn"]  # type: ignore[return-value]


def _saved_message(saved: str | None) -> str:
    return {
        "triage": "Ticket changes saved.",
        "draft": "Draft response saved.",
    }.get(saved or "", "")


@app.get("/health")
def health() -> dict[str, str]:
    """Small readiness endpoint used by the test harness."""
    return {"status": "ok"}


@app.get("/")
def ticket_list(
    request: Request,
    status: Status | None = Query(None),
    category: Category | None = Query(None),
    priority: Priority | None = Query(None),
):
    """Ticket list page with optional status / category / priority filters."""
    filters = TicketFilters(status=status, category=category, priority=priority)
    tickets = database.list_tickets(_conn(), filters)
    return templates.TemplateResponse(
        request,
        "ticket_list.html",
        {
            "tickets": tickets,
            "filters": filters,
            "all_statuses": list(Status),
            "all_categories": list(Category),
            "all_priorities": list(Priority),
            "total_count": database.count_tickets(_conn()),
        },
    )


@app.get("/tickets/{ticket_id}")
def ticket_detail(request: Request, ticket_id: str, saved: str | None = None):
    """Detail page for a single ticket."""
    ticket = database.get_ticket(_conn(), ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return templates.TemplateResponse(
        request,
        "ticket_detail.html",
        {
            "ticket": ticket,
            "all_categories": list(Category),
            "all_priorities": list(Priority),
            "all_statuses": list(Status),
            "flash": _saved_message(saved),
        },
    )


@app.post("/tickets/{ticket_id}/triage")
def update_triage(
    ticket_id: str,
    category: Category = Form(...),
    priority: Priority = Form(...),
    status: Status = Form(...),
):
    """Change category, priority and/or status from the dashboard UI."""
    if database.get_ticket(_conn(), ticket_id) is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    database.update_ticket_fields(
        _conn(), ticket_id, category=category, priority=priority, status=status
    )
    return RedirectResponse(
        url=f"/tickets/{ticket_id}?saved=triage", status_code=303
    )


@app.post("/tickets/{ticket_id}/draft")
def save_draft(ticket_id: str, draft_response: str = Form(...)):
    """Save a draft response for a ticket (nothing is ever sent)."""
    if database.get_ticket(_conn(), ticket_id) is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    database.save_draft_response(_conn(), ticket_id, draft_response)
    return RedirectResponse(url=f"/tickets/{ticket_id}?saved=draft", status_code=303)


def main() -> None:
    """Start the development server (``python -m app.main``)."""
    import uvicorn

    host = config.get_host()
    port = config.get_port()
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
