from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise
import logging
from db_config import TORTOISE_ORM

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
logging.getLogger("conversation").setLevel(logging.INFO)
logging.getLogger("pdfgen").setLevel(logging.DEBUG)
logging.getLogger("uvicorn").setLevel(logging.INFO)  # Keep uvicorn at INFO level to reduce noise
logging.getLogger("file_upload").setLevel(logging.DEBUG)  # Set file upload logger to DEBUG
logging.getLogger("upload").setLevel(logging.DEBUG)  # Set upload router logger to DEBUG

# Disable Tortoise and database-related debug logs
logging.getLogger("tortoise").setLevel(logging.WARNING)
logging.getLogger("tortoise.db_client").setLevel(logging.WARNING)
logging.getLogger("db").setLevel(logging.WARNING)
logging.getLogger("asyncpg").setLevel(logging.WARNING)
logging.getLogger("tortoise.backends").setLevel(logging.WARNING)

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
from routers import upload, conversation, pdfgen, projects, auth, cover_page
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(conversation.router, prefix="/conversation", tags=["conversation"])
app.include_router(pdfgen.router, prefix="/documents", tags=["pdf"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(cover_page.router, prefix="/cover-page", tags=["cover-page"])

# Register Tortoise ORM using the config from db_config.py
register_tortoise(
    app,
    config=TORTOISE_ORM,
    generate_schemas=False,  # Don't generate schemas - let Aerich handle migrations
    add_exception_handlers=True,
)

@app.get("/ping")
async def ping():
    return {"status": "ok"}