from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise
from config import settings
import logging

# Configure logging to show debug logs
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Set log levels for specific loggers
logging.getLogger("pdf_renderer").setLevel(logging.DEBUG)
logging.getLogger("conversation").setLevel(logging.DEBUG)
logging.getLogger("pdfgen").setLevel(logging.DEBUG)
logging.getLogger("uvicorn").setLevel(logging.INFO)  # Keep uvicorn at INFO level to reduce noise

app = FastAPI(
    title="Erdbaron Document Generator",
    description="API for AI-guided document creation with persistence",
    version="0.1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from routers import upload, conversation, pdfgen, projects
# app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(conversation.router, prefix="/conversation", tags=["conversation"])
app.include_router(pdfgen.router, prefix="/documents", tags=["pdf"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])

# Register Tortoise ORM
register_tortoise(
    app,
    db_url=settings.DATABASE_URL,
    modules={"models": ["models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

@app.get("/ping")
async def ping():
    return {"status": "ok"}