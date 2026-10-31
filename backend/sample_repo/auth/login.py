"""Login flow: validate credentials and open a session."""
from db.database import get_user, save_session
from utils.security import generate_token, verify_password

MAX_ATTEMPTS = 5
_failed_attempts = {}


def validate_credentials(email, password):
    """Return the user record when the email/password pair is valid, otherwise None."""
    if not email or not password:
        return None
    user = get_user(email)
    if user is None:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def create_session(user):
    """Create a session token for an authenticated user and persist it."""
    token = generate_token()
    save_session(user["id"], token)
    return token


def login(email, password):
    """Authenticate a user and return a session token or an error response."""
    attempts = _failed_attempts.get(email, 0)
    if attempts >= MAX_ATTEMPTS:
        return {"status": 429, "error": "Too many failed attempts"}
    user = validate_credentials(email, password)
    if user is None:
        _failed_attempts[email] = attempts + 1
        return {"status": 401, "error": "Invalid email or password"}
    _failed_attempts.pop(email, None)
    token = create_session(user)
    return {"status": 200, "token": token, "user": {"id": user["id"], "name": user["name"]}}
