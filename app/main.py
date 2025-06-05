from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.routes import news
from contextlib import asynccontextmanager
from app.services.redis import close_redis
from fastapi.middleware.cors import CORSMiddleware
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    await close_redis()


load_dotenv()
origins = os.getenv("ALLOWED_ORIGINS")
app = FastAPI(lifespan=lifespan, title="NewsGuardian.AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(news.router, prefix="/api/v1", tags=["news"])


@app.get("/")
def check_root():
    return {"status": "OK", "message": "NewsGuardian.AI API is up and running!"}
