"""Production WSGI entry point for TripMate."""

from tripmate import create_app


app = create_app()
