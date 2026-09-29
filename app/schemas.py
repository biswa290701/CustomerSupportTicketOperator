"""Typed data models and controlled vocabularies for support tickets."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT_ACCESS = "account_access"
    REFUND = "refund"
    GENERAL = "general"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Status(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Ticket(BaseModel):
    """A single customer support ticket."""

    id: str = Field(..., examples=["TCK-1001"])
    customer_name: str
    subject: str
    description: str
    category: Category
    priority: Priority
    status: Status
    created_at: str  # ISO-8601 UTC timestamp
    draft_response: str | None = None


class TicketFilters(BaseModel):
    """Filter set used by the ticket list page."""

    status: Status | None = None
    category: Category | None = None
    priority: Priority | None = None

    def as_query_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.status is not None:
            params["status"] = self.status.value
        if self.category is not None:
            params["category"] = self.category.value
        if self.priority is not None:
            params["priority"] = self.priority.value
        return params
