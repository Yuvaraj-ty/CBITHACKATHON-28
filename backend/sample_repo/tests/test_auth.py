from auth.login import login, validate_credentials
from auth.register import register_user, validate_password
from db.database import init_schema


def test_validate_password_rules():
    assert validate_password("short1") is False
    assert validate_password("longenough1") is True


def test_register_then_login():
    init_schema()
    register_user("test@example.com", "password123", "Tester")
    result = login("test@example.com", "password123")
    assert result["status"] == 200


def test_invalid_credentials():
    assert validate_credentials("nobody@example.com", "nope") is None
