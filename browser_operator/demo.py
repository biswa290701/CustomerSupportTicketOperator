"""Runnable end-to-end demonstration of the Stage 1 acceptance criteria.

Start the web application first, then run::

    python -m browser_operator.demo --ticket TCK-1001 --priority high

The script launches Chromium, opens the dashboard, locates the ticket,
changes its priority through the UI, re-reads the UI to verify the change and
saves a draft response. Screenshots land in ``evidence/screenshots`` and the
action log in ``evidence/logs``.
"""

from __future__ import annotations

import argparse
import sys

from browser_operator.browser_operator import TicketOperator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the browser operator demo.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ticket", default="TCK-1001", help="Ticket id to operate on")
    parser.add_argument("--priority", default="high", help="New priority to apply")
    parser.add_argument("--status", default=None, help="Optional new status")
    parser.add_argument("--headed", action="store_true", help="Show the browser window")
    parser.add_argument(
        "--draft",
        default=(
            "Hi, thanks for reaching out. We have reviewed ticket {ticket} and "
            "are following up with our billing team. We will get back to you "
            "within one business day."
        ),
        help="Draft response text to save",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    with TicketOperator(args.base_url, headless=not args.headed) as op:
        op.open_dashboard()

        if not op.locate_ticket(args.ticket):
            print(f"FAILED: ticket {args.ticket} not found in the list", file=sys.stderr)
            return 1

        before = op.inspect_ticket(args.ticket)
        if not before.found:
            print(f"FAILED: could not open {args.ticket}", file=sys.stderr)
            return 1
        print(f"Inspected {before.ticket_id}: priority={before.priority} status={before.status}")

        update = op.update_ticket(
            args.ticket, priority=args.priority, status=args.status
        )
        print(f"Update result: {update.result} ({update.detail})")
        if update.result == "error":
            return 1

        after = op.inspect_ticket(args.ticket)
        if after.priority != args.priority:
            print(
                f"FAILED: expected priority={args.priority}, UI shows {after.priority}",
                file=sys.stderr,
            )
            return 1
        print(f"Verified in UI: {after.ticket_id} priority={after.priority}")

        draft_text = args.draft.format(ticket=args.ticket)
        draft = op.save_draft_response(args.ticket, draft_text)
        print(f"Draft result: {draft.result} ({draft.detail})")
        if draft.result == "error":
            return 1

        final = op.inspect_ticket(args.ticket)
        print(
            f"Final UI state: {final.ticket_id} priority={final.priority} "
            f"status={final.status} draft_chars={len(final.draft_response or '')}"
        )
        print(f"Screenshots: {op.screenshot_dir}")
        print(f"Action log:  {op.logger.log_path}")

    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
