"""Pytest bootstrap — use in-memory SQLite for unit tests only."""

import os

# Unit tests must not require a live Supabase connection.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
