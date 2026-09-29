# Customer Support Ticket Operator — Stage 1

A small, locally hosted **customer support ticket dashboard** plus a
**Python Playwright browser operator** that drives it through the real
Chromium UI.

Stage 1 is intentionally simple: no LLM, no approval workflow, no email
sending. Everything the operator changes, it changes by clicking and typing in
a browser.

---

## 1. What is in this repository

```
app/                      FastAPI + Jinja2 web application
  config.py               host / port / database path from env and .env
  schemas.py              Pydantic models and the controlled vocabularies
  database.py             SQLite connection, schema and queries
  seed.py                 9 synthetic tickets, inserted idempotently
  main.py                 routes: list, filters, detail, triage, draft
  templates/              Jinja2 templates (ticket_list, ticket_detail)
  static/style.css        minimal styling

browser_operator/         Playwright operator (browser UI only)
  browser_operator.py     navigation, inspection, updates, draft saving
  action_log.py           timestamped action log (console + .log + .jsonl)
  demo.py                 runnable end-to-end demonstration

tests/                    pytest suite
  test_seeding.py         seeding is reproducible and never duplicates
  test_filtering.py       list, filters, detail page, forms
  test_operator.py        real Chromium operator behaviour (marked `operator`)

evidence/                 screenshots + action logs (created at run time, git-ignored)
data/tickets.db           SQLite database (created at run time, git-ignored)
```

Everything is synthetic: names, ticket text and identifiers are invented for
this assignment. **No email or external message is ever sent**, and the
application needs **no LLM API key**.

---

## 2. Requirements

* Windows 10/11 with **PowerShell**
* Python **3.11 or newer** (`py -0p` shows the installed versions)

---

## 3. Setup (Windows PowerShell)

Open PowerShell **in the project folder** and run these commands exactly.

### 3.1 Create the virtual environment

```powershell
py -3.11 -m venv .venv
```

If your machine only has a newer Python, use that instead, e.g. `py -3.14 -m venv .venv`.

### 3.2 Install the Python dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> If script execution is blocked by policy, run the two `.\.venv\Scripts\...`
> commands above — they do not need activation. To activate instead:
> `Set-ExecutionPolicy -Scope Process RemoteSigned` then `.\.venv\Scripts\Activate.ps1`.

### 3.3 Install the Chromium browser for Playwright

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

### 3.4 (Optional) local configuration

```powershell
Copy-Item .env.example .env
```

The defaults (`127.0.0.1:8000`, `data/tickets.db`) work as-is.

---

## 4. Running the application

```powershell
.\.venv\Scripts\python.exe -m app.main
```

Then open <http://127.0.0.1:8000/>.

* The database is created and seeded with **9 synthetic tickets** on start.
* Seeding is **idempotent**: restarting the app never duplicates tickets and
  never resets changes you already made.
* To wipe all data, stop the app and delete `data\tickets.db`.

Endpoints:

| Method | Path                       | Purpose                                   |
|--------|----------------------------|-------------------------------------------|
| GET    | `/`                        | ticket list + `status` / `category` / `priority` filters |
| GET    | `/tickets/{id}`            | ticket detail page                         |
| POST   | `/tickets/{id}/triage`     | change category, priority and/or status    |
| POST   | `/tickets/{id}/draft`      | save a draft response                      |
| GET    | `/health`                  | readiness check used by the test harness   |

---

## 5. Running the browser operator

With the application still running in one PowerShell window, open a **second**
window in the same folder and run:

```powershell
.\.venv\Scripts\python.exe -m browser_operator.demo
```

Useful options:

```powershell
# choose the ticket and the new priority
.\.venv\Scripts\python.exe -m browser_operator.demo --ticket TCK-1003 --priority medium

# watch the browser
.\.venv\Scripts\python.exe -m browser_operator.demo --headed

# another base URL
.\.venv\Scripts\python.exe -m browser_operator.demo --base-url http://127.0.0.1:9000
```

What the demo does (all through the browser UI):

1. launches Chromium and opens the dashboard,
2. locates the requested ticket in the list,
3. inspects its current state on the detail page,
4. changes its priority through the form and **re-reads the UI to verify**,
5. saves a draft response and verifies it again.

Artefacts:

* `evidence\screenshots\` — one screenshot after each meaningful action,
* `evidence\logs\operator-<run>.log` — human readable action log
  (`timestamp | ticket | action | result | detail | error`),
* `evidence\logs\operator-<run>.jsonl` — the same records as JSON lines.

The operator **never** touches the database or calls the HTTP API directly;
it only uses stable `data-testid` selectors in the page.

---

## 6. Running the tests

```powershell
# everything (seeding + filtering + browser operator)
.\.venv\Scripts\python.exe -m pytest

# application-only tests, no browser required
.\.venv\Scripts\python.exe -m pytest -m "not operator"

# only the browser-operator tests (Chromium must be installed)
.\.venv\Scripts\python.exe -m pytest -m operator

# verbose
.\.venv\Scripts\python.exe -m pytest -v
```

The browser tests start their own uvicorn server on a free port with a
throw-away database, so they never disturb your local `data\tickets.db`.

---

## 7. Acceptance checklist

| # | Criterion | How it is covered |
|---|-----------|-------------------|
| 1 | App starts locally and shows seeded tickets | `python -m app.main` → `/` shows 9 rows; `test_list_shows_all_seeded_tickets` |
| 2 | Operator opens Chromium and finds a ticket | `browser_operator.demo`; `test_operator_launches_and_finds_ticket` |
| 3 | Operator changes a priority through the browser and verifies it | `test_operator_changes_priority_and_verifies_via_ui` |
| 4 | A response can be saved as a draft through the browser | `test_operator_saves_draft_response` |
| 5 | Restarting does not duplicate seeded tickets | `test_app_restart_does_not_duplicate_tickets` |
| 6 | README has exact install / run / test commands | this file, sections 3–6 |

---

## 8. Troubleshooting

* **`Executable doesn't exist ... chromium`** — run
  `.\.venv\Scripts\python.exe -m playwright install chromium`.
* **Port already in use** — set another port in `.env` (`APP_PORT=8100`) or
  stop the process that owns port 8000.
* **PowerShell blocks `Activate.ps1`** — run
  `Set-ExecutionPolicy -Scope Process RemoteSigned`, or skip activation and
  call `.\.venv\Scripts\python.exe` directly as shown above.
* **Want a clean slate** — stop the app and delete `data\tickets.db`; the next
  start reseeds from `app\seed.py`.
* **Old screenshots/logs** — delete the `evidence` folder; it is recreated
  automatically.

---

## 9. Scope

Implemented in Stage 1: local dashboard, SQLite persistence with safe
seeding, list/detail/filters, triage and draft forms, the Playwright
operator, action logging, screenshots and tests.

Deliberately **not** implemented yet: the LLM planner, the approval workflow
and advanced recovery — these belong to later stages.

## Licence

MIT — see [LICENSE](LICENSE).
