"""Timestamped action logging for the browser operator.

Each operator action is written to
  * the console (so a human can follow the run), and
  * ``evidence/logs/operator-<run_id>.log``  (human readable), and
  * ``evidence/logs/operator-<run_id>.jsonl`` (one JSON object per action).

Fields recorded for every action: timestamp, ticket id, action, result and
error information (when applicable).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class ActionRecord:
    timestamp: str
    ticket_id: str
    action: str
    result: str
    detail: str = ""
    error: str | None = None

    def as_line(self) -> str:
        return (
            f"{self.timestamp} | ticket={self.ticket_id} | action={self.action} "
            f"| result={self.result} | detail={self.detail} "
            f"| error={self.error or '-'}"
        )


class ActionLogger:
    """Small append-only logger used by :class:`browser_operator.browser_operator`."""

    def __init__(self, log_dir: Path, run_id: str | None = None) -> None:
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_dir / f"operator-{self.run_id}.log"
        self.jsonl_path = log_dir / f"operator-{self.run_id}.jsonl"
        self.records: list[ActionRecord] = []

    def log(
        self,
        action: str,
        *,
        ticket_id: str = "-",
        result: str = "ok",
        detail: str = "",
        error: str | None = None,
    ) -> ActionRecord:
        record = ActionRecord(
            timestamp=_now(),
            ticket_id=ticket_id,
            action=action,
            result=result,
            detail=detail,
            error=error,
        )
        self.records.append(record)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(record.as_line() + "\n")
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record)) + "\n")
        print(record.as_line(), flush=True)
        return record
