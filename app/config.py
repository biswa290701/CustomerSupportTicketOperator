"""Application configuration.

Values are resolved in this order:
  1. real environment variables
  2. a local ``.env`` file (if present)
  3. built-in defaults

No LLM / external API keys are required to run Stage 1.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "tickets.db"
EVIDENCE_DIR = PROJECT_ROOT / "evidence"


def _load_dotenv(path: Path) -> None:
    """Tiny ``.env`` reader so we do not need an extra dependency."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Real environment variables always win over the .env file.
        os.environ.setdefault(key, value)


_load_dotenv(PROJECT_ROOT / ".env")


def get_host() -> str:
    return os.environ.get("APP_HOST", DEFAULT_HOST)


def get_port() -> int:
    return int(os.environ.get("APP_PORT", DEFAULT_PORT))


def get_db_path() -> Path:
    raw = os.environ.get("TICKET_DB_PATH")
    path = Path(raw) if raw else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path
