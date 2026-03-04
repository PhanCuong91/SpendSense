"""
Security utilities for the application.
Currently lightweight, but ready to expand for:
- JWT authentication
- API keys
- Request signature validation
- Secret encryption (at rest)
"""

from hashlib import sha256


def hash_string(value: str) -> str:
    """Simple deterministic hashing."""
    if not value:
        return ""
    return sha256(value.encode("utf-8")).hexdigest()