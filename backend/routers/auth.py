import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from lib.auth import clear_session, current_user, hash_password, set_session, verify_password
from lib.llm import provider_info
from lib.parser import PARSED_LANGUAGES
from lib.sqldb import execute, now_iso, query_one
from models.schemas import LoginIn, RegisterIn, SystemStatus, UserOut

router = APIRouter()


@router.post("/auth/register", response_model=UserOut)
async def register(body: RegisterIn, request: Request, response: Response):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    if query_one("SELECT id FROM users WHERE email = ?", (email,)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    uid = str(uuid.uuid4())
    created = now_iso()
    execute("INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?,?,?,?,?)",
            (uid, email, body.name.strip(), hash_password(body.password), created))
    set_session(request, response, uid)
    return UserOut(id=uid, email=email, name=body.name.strip(), created_at=created)


@router.post("/auth/login", response_model=UserOut)
async def login(body: LoginIn, request: Request, response: Response):
    user = query_one("SELECT * FROM users WHERE email = ?", (body.email.strip().lower(),))
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    set_session(request, response, user["id"])
    return UserOut(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])


@router.post("/auth/logout")
async def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return UserOut(**user)


@router.get("/system/status", response_model=SystemStatus)
async def system_status():
    info = provider_info()
    return SystemStatus(**info, parsed_languages=PARSED_LANGUAGES, embedding="Local TF-IDF + LSA vectors (scikit-learn)")
