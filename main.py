from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings

app = FastAPI(
    title="Erdbaron Document Generator",
    description="API for AI-guided document creation",
    version="0.1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from routers import upload, conversation, pdfgen
app.include_router(conversation.router, prefix="/conversation", tags=["conversation"])
# app.include_router(upload.router, prefix="/upload", tags=["upload"])
#app.include_router(pdfgen.router, prefix="/documents", tags=["pdf"])

@app.get("/ping")
async def ping():
    return {"status": "ok"}