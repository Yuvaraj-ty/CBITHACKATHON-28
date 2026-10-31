"""Password hashing and token helpers."""
import hashlib
import hmac
import os
import secrets

ITERATIONS = 120_000


def hash_password(password, salt=None):
    """Hash a password with PBKDF2-SHA256 and a random salt."""
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return salt.hex() + ":" + digest.hex()


def verify_password(password, stored):
    """Compare a password with a stored hash in constant time."""
    salt_hex, digest_hex = stored.split(":")
    candidate = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate.split(":")[1], digest_hex)


def generate_token(length=32):
    """Generate a random URL-safe session token."""
    return secrets.token_urlsafe(length)
