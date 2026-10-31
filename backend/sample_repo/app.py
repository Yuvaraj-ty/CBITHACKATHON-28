"""HTTP entry points for the demo auth service."""
from auth.login import login
from auth.register import register_user
from db.database import init_schema


def handle_request(method, path, payload):
    """Route an incoming request to the matching handler."""
    if method != "POST":
        return {"status": 405, "error": "Method not allowed"}
    if path == "/login":
        return login(payload.get("email", ""), payload.get("password", ""))
    if path == "/register":
        return register_user(payload.get("email", ""), payload.get("password", ""), payload.get("name", ""))
    return {"status": 404, "error": "Not found"}


def main():
    init_schema()
    print(handle_request("POST", "/register", {"email": "ada@example.com", "password": "s3cret!!", "name": "Ada"}))
    print(handle_request("POST", "/login", {"email": "ada@example.com", "password": "s3cret!!"}))


if __name__ == "__main__":
    main()
