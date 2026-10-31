"""Registration flow: validate input, hash the password, store the user."""
import re

from db.database import get_user, insert_user
from utils.security import hash_password

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def validate_email(email):
    """Check the email has a plausible format."""
    return bool(EMAIL_RE.match(email or ""))


def validate_password(password):
    """Passwords need at least 8 characters and one digit."""
    if len(password) < 8:
        return False
    for ch in password:
        if ch.isdigit():
            return True
    return False


def register_user(email, password, name):
    """Create a new account after validating the email and password."""
    if not validate_email(email):
        return {"status": 422, "error": "Invalid email"}
    if not validate_password(password):
        return {"status": 422, "error": "Password too weak"}
    if get_user(email) is not None:
        return {"status": 409, "error": "Email already registered"}
    user_id = insert_user(email, hash_password(password), name)
    return {"status": 201, "user": {"id": user_id, "name": name}}
