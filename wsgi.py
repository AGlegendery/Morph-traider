"""Standard WSGI entrypoint for shared hosting (Passenger, LiteSpeed, Gunicorn, uWSGI)."""

from __future__ import annotations

from app import create_app

application = create_app()
app = application
