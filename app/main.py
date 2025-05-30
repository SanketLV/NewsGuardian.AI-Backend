from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.routes import news
import os

load_dotenv()
app = FastAPI(title="NewsGuardian.AI", version="1.0.0")

gnews_api_key = os.getenv("GNEWS_API_KEY")


# Include routers
app.include_router(news.router)


@app.get("/")
def check_root():
    return {"status": "OK", "message": "NewsGuardian.AI API is up and running!"}
