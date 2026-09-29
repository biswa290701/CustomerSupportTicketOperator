"""Browser operator package (Stage 1).

Everything in this package drives the dashboard through the Chromium UI.
It never imports the web application's database or HTTP layer.

The package is deliberately *not* named ``operator``: that name belongs to
the Python standard library and shadowing it would break FastAPI / Pydantic.
"""
