import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from lib.db import client, ensure_indexes
from lib.sqldb import init_db
from routers import ai, auth, quiz, repos


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.index_task = asyncio.create_task(ensure_indexes())
    yield
    client.close()


app = FastAPI(lifespan=lifespan, title="CodeAtlas API")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "CodeAtlas API"}


api_router.include_router(auth.router)
api_router.include_router(repos.router)
api_router.include_router(ai.router)
api_router.include_router(quiz.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Include the router in the main app - keep last
app.include_router(api_router)
