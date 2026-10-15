"""Production WSGI entrypoint.

Run with:  python wsgi.py
(or behind any WSGI server:  waitress-serve wsgi:app)
"""
import os

from dotenv import load_dotenv
from waitress import serve

from app import HOST, PORT, app

load_dotenv()

if __name__ == "__main__":
    serve(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=PORT,
        threads=8,
        channel_timeout=120,
    )
