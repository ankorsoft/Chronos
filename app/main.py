"""
FastAPI application entry point for Chronos Context.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import create_db_and_tables
from app.api.router import api_router, root_router


# Create FastAPI app
app = FastAPI(
    title="Chronos Context",
    description="AI-powered project analysis & context generation API for LLM integration.",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    create_db_and_tables()


# Mount static files
from app.api import STATIC_DIR
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(root_router)
app.include_router(api_router, prefix="/api/v1")
