"""Environment readers shared by the existing processes; no network at import."""

import os


def ascon_key():
    value = os.environ.get("ASCON_KEY_HEX", "")
    try:
        key = bytes.fromhex(value)
    except ValueError:
        raise ValueError("ASCON_KEY_HEX must contain 32 hexadecimal characters") from None
    if len(value) != 32 or len(key) != 16:
        raise ValueError("ASCON_KEY_HEX must contain 32 hexadecimal characters")
    return key


def database_url(value=None):
    # Explicit driver: SQLAlchemy 2.0 otherwise defaults to psycopg2.
    value = os.environ.get("DATABASE_URL", "") if value is None else value
    if value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+psycopg://", 1)
    if not value.startswith("postgresql+psycopg://"):
        raise ValueError("DATABASE_URL must use postgresql+psycopg://")
    return value
