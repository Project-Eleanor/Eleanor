"""Password hashing utilities using bcrypt directly."""

import bcrypt


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    # bcrypt 5.0+ enforces 72-byte limit strictly - truncate to be safe
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed: bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    # bcrypt 5.0+ enforces 72-byte limit strictly - truncate to be safe
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    result: bool = bcrypt.checkpw(password_bytes, hashed_bytes)
    return result
