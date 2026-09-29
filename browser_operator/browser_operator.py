"""Playwright browser operator for the local support dashboard.

Design rules for Stage 1
------------------------
* Every change goes through the real browser UI (no direct database access,
  no HTTP API calls performed on behalf of the operator).
* All selectors are stable ``data-testid`` attributes.
* The current state is always inspected *before* a change, and unchanged
  values are skipped so we never issue pointless writes.
* After every meaningful action a screenshot is stored under
  ``evidence/screenshots`` and the action is written to the action log.

Usage::

    from browser_operator import TicketOperator

    with TicketOperator("http://127.0.0.1:8000") as op:
        op.open_dashboard()
        op.locate_ticket("TCK-1001")
        op.update_ticket("TCK-1001", priority="high")
        op.save_draft_response("TCK-1001", "Hello, we are checking this now.")
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Browser, Page, Playwright, sync_playwright
from pydantic import BaseModel, Field

from browser_operator.action_log import ActionLogger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "evidence"

LIST_TESTID = "ticket-list"
SCREENSHOT_DIRNAME = "screenshots"
LOG_DIRNAME = "logs"

VALID_CATEGORIES = {"billing", "technical", "account_access", "refund", "general"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_STATUSES = {"open", "in_progress", "pending", "resolved", "closed"}


class TicketState(BaseModel):
    """Snapshot of a ticket as read back from the browser UI."""

    ticket_id: str
    found: bool = False
    subject: str | None = None
    customer_name: str | None = None
    category: str | None = None
    priority: str | None = None
    status: str | None = None
    created_at: str | None = None
    draft_response: str | None = None


class OperationResult(BaseModel):
    """Outcome of a single operator action."""

    action: str
    ticket_id: str
    result: str  # "updated" | "skipped" | "error"
    changes: dict[str, str] = Field(default_factory=dict)
    detail: str = ""
    error: str | None = None
    screenshot: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_name(text: str) -> str:
    """Make free text safe to use inside a file name."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "action"


class TicketOperator:
    """Drives the support dashboard through Chromium."""

    def __init__(
        self,
        base_url: str,
        *,
        headless: bool = True,
        evidence_dir: Path | str | None = None,
        timeout_ms: int = 15_000,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.evidence_dir = Path(evidence_dir) if evidence_dir else DEFAULT_EVIDENCE_DIR
        self.screenshot_dir = self.evidence_dir / SCREENSHOT_DIRNAME
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._shot_counter = 0
        self.logger = ActionLogger(self.evidence_dir / LOG_DIRNAME)

    # ------------------------------------------------------------------ setup
    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Operator is not started. Use it as a context manager.")
        return self._page

    def start(self) -> "TicketOperator":
        """Launch Chromium and open a fresh page."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        context = self._browser.new_context(viewport={"width": 1440, "height": 950})
        self._page = context.new_page()
        self._page.set_default_timeout(self.timeout_ms)
        self.logger.log(
            "launch_browser",
            detail=f"base_url={self.base_url} headless={self.headless}",
        )
        return self

    def stop(self) -> None:
        """Close Chromium and the Playwright driver."""
        try:
            if self._browser is not None:
                self._browser.close()
            if self._playwright is not None:
                self._playwright.stop()
            self.logger.log("shutdown_browser")
        finally:
            self._browser = None
            self._playwright = None
            self._page = None

    def __enter__(self) -> "TicketOperator":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # -------------------------------------------------------------- utilities
    def screenshot(self, action: str, ticket_id: str = "-") -> Path:
        """Store a screenshot of the current page and return its path."""
        self._shot_counter += 1
        name = (
            f"{self._shot_counter:02d}_{_utc_now()}_"
            f"{_safe_name(action)}_{_safe_name(ticket_id)}.png"
        )
        path = self.screenshot_dir / name
        self.page.screenshot(path=str(path))
        return path

    def _text(self, testid: str) -> str:
        return self.page.locator(f"[data-testid='{testid}']").inner_text().strip()

    def _draft_text(self) -> str:
        """Exact (un-normalised) text of the saved draft element."""
        value = self.page.locator("[data-testid='ticket-draft']").text_content()
        return value or ""

    # ------------------------------------------------------------- navigation
    def navigate_to_ticket_list(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
    ) -> None:
        """Open the ticket list, optionally with status/category/priority filters."""
        params = [
            f"{key}={value}"
            for key, value in (("status", status), ("category", category), ("priority", priority))
            if value
        ]
        url = self.base_url + "/" + ("?" + "&".join(params) if params else "")
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_selector(f"[data-testid='{LIST_TESTID}']")
        self.logger.log("navigate_to_ticket_list", detail=f"url={url}")

    def open_dashboard(self) -> None:
        """Open the dashboard root (unfiltered ticket list) and capture it."""
        self.navigate_to_ticket_list()
        shot = self.screenshot("open_dashboard")
        self.logger.log("open_dashboard", detail=f"screenshot={shot.name}")

    def locate_ticket(
        self,
        ticket_id: str,
        *,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
    ) -> bool:
        """Return True when the given ticket row is visible on the list page."""
        self.navigate_to_ticket_list(status=status, category=category, priority=priority)
        found = self.page.locator(f"[data-testid='ticket-row-{ticket_id}']").count() > 0
        shot = self.screenshot("locate_ticket", ticket_id)
        self.logger.log(
            "locate_ticket",
            ticket_id=ticket_id,
            result="found" if found else "not_found",
            detail=f"screenshot={shot.name}",
        )
        return found

    # ---------------------------------------------------------------- reading
    def inspect_ticket(self, ticket_id: str) -> TicketState:
        """Navigate to the ticket detail page and read its current state."""
        url = f"{self.base_url}/tickets/{ticket_id}"
        response = self.page.goto(url, wait_until="domcontentloaded")

        if response is not None and response.status == 404:
            self.logger.log(
                "inspect_ticket",
                ticket_id=ticket_id,
                result="not_found",
                detail="http_status=404",
            )
            return TicketState(ticket_id=ticket_id, found=False)

        self.page.wait_for_selector("[data-testid='ticket-id']")
        state = TicketState(
            ticket_id=self._text("ticket-id"),
            found=True,
            subject=self._text("ticket-subject"),
            customer_name=self._text("ticket-customer"),
            category=self._text("ticket-category"),
            priority=self._text("ticket-priority"),
            status=self._text("ticket-status"),
            created_at=self._text("ticket-created-at"),
            draft_response=self._draft_text(),
        )
        self.logger.log(
            "inspect_ticket",
            ticket_id=ticket_id,
            result="ok",
            detail=(
                f"category={state.category} priority={state.priority} "
                f"status={state.status} draft={'yes' if state.draft_response else 'no'}"
            ),
        )
        return state

    # ---------------------------------------------------------------- writing
    def update_ticket(
        self,
        ticket_id: str,
        *,
        category: str | None = None,
        priority: str | None = None,
        status: str | None = None,
    ) -> OperationResult:
        """Change category / priority / status through the detail-page form.

        The current state is read first; fields that already hold the requested
        value are never written again.
        """
        requested = {"category": category, "priority": priority, "status": status}

        try:
            self._validate(requested)
            current = self.inspect_ticket(ticket_id)
            if not current.found:
                return self._fail(
                    "update_ticket", ticket_id, "detail page returned 404", "Ticket not found"
                )

            changes = {
                name: value
                for name, value in requested.items()
                if value is not None and getattr(current, name) != value
            }
            if not changes:
                self.logger.log(
                    "update_ticket",
                    ticket_id=ticket_id,
                    result="skipped",
                    detail="already in the requested state",
                )
                return OperationResult(
                    action="update_ticket",
                    ticket_id=ticket_id,
                    result="skipped",
                    detail="already in the requested state",
                )

            for name, value in changes.items():
                self.page.select_option(f"[data-testid='select-{name}']", value)

            self.page.click("[data-testid='save-triage']")
            self.page.wait_for_selector("[data-testid='flash-message']")

            after = self.inspect_ticket(ticket_id)
            mismatches = {
                name: value for name, value in changes.items() if getattr(after, name) != value
            }
            shot = self.screenshot("update_ticket", ticket_id)

            if mismatches:
                return self._fail(
                    "update_ticket",
                    ticket_id,
                    f"UI verification failed: {mismatches}",
                    "Verification failed",
                    changes=changes,
                    screenshot=shot,
                )

            detail = ", ".join(
                f"{name}: {getattr(current, name)} -> {value}" for name, value in changes.items()
            )
            self.logger.log(
                "update_ticket",
                ticket_id=ticket_id,
                result="updated",
                detail=f"{detail}; screenshot={shot.name}",
            )
            return OperationResult(
                action="update_ticket",
                ticket_id=ticket_id,
                result="updated",
                changes=changes,
                detail=detail,
                screenshot=str(shot),
            )
        except Exception as exc:  # noqa: BLE001 - recorded before re-raising
            self.logger.log(
                "update_ticket", ticket_id=ticket_id, result="error", error=str(exc)
            )
            raise

    def save_draft_response(self, ticket_id: str, text: str) -> OperationResult:
        """Write a draft response into the detail page and save it."""
        try:
            current = self.inspect_ticket(ticket_id)
            if not current.found:
                return self._fail(
                    "save_draft_response",
                    ticket_id,
                    "detail page returned 404",
                    "Ticket not found",
                )

            if current.draft_response == text:
                self.logger.log(
                    "save_draft_response",
                    ticket_id=ticket_id,
                    result="skipped",
                    detail="draft already identical",
                )
                return OperationResult(
                    action="save_draft_response",
                    ticket_id=ticket_id,
                    result="skipped",
                    detail="draft already identical",
                )

            self.page.fill("[data-testid='draft-response']", text)
            self.page.click("[data-testid='save-draft']")
            self.page.wait_for_selector("[data-testid='flash-message']")

            after = self.inspect_ticket(ticket_id)
            shot = self.screenshot("save_draft_response", ticket_id)

            if after.draft_response != text:
                return self._fail(
                    "save_draft_response",
                    ticket_id,
                    "draft text did not persist in the UI",
                    "Verification failed",
                    screenshot=shot,
                )

            self.logger.log(
                "save_draft_response",
                ticket_id=ticket_id,
                result="updated",
                detail=f"chars={len(text)}; screenshot={shot.name}",
            )
            return OperationResult(
                action="save_draft_response",
                ticket_id=ticket_id,
                result="updated",
                changes={"draft_response": text},
                detail=f"saved {len(text)} characters",
                screenshot=str(shot),
            )
        except Exception as exc:  # noqa: BLE001 - recorded before re-raising
            self.logger.log(
                "save_draft_response", ticket_id=ticket_id, result="error", error=str(exc)
            )
            raise

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _validate(requested: dict[str, str | None]) -> None:
        allowed = {
            "category": VALID_CATEGORIES,
            "priority": VALID_PRIORITIES,
            "status": VALID_STATUSES,
        }
        for name, value in requested.items():
            if value is None:
                continue
            if value not in allowed[name]:
                raise ValueError(
                    f"Invalid {name} '{value}'. Allowed: {sorted(allowed[name])}"
                )

    def _fail(
        self,
        action: str,
        ticket_id: str,
        detail: str,
        error: str,
        changes: dict[str, str] | None = None,
        screenshot: Path | None = None,
    ) -> OperationResult:
        self.logger.log(
            action, ticket_id=ticket_id, result="error", detail=detail, error=error
        )
        return OperationResult(
            action=action,
            ticket_id=ticket_id,
            result="error",
            changes=changes or {},
            detail=detail,
            error=error,
            screenshot=str(screenshot) if screenshot else None,
        )
