import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
load_dotenv()

from routers import upload, status, result, jobs, thumbnail, billing, admin, qa, quota
from utils.logging_config import setup_logging


setup_logging()

app = FastAPI(
    title="VidIQ API",
    description="AI Video Intelligence backend",
    version="1.0.0"
)

_cors_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(status.router)
app.include_router(result.router)
app.include_router(jobs.router)
app.include_router(thumbnail.router)
app.include_router(billing.router)
app.include_router(admin.router)
app.include_router(qa.router)
app.include_router(quota.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "vidiq-api"}