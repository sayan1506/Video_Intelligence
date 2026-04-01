from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import upload, status, result

load_dotenv()


app = FastAPI(
    title="VidIQ API",
    description="AI Video Intelligence backend",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(upload.router)
app.include_router(status.router)
app.include_router(result.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "vidiq-api"}