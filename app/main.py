"""
app/main.py

FastAPI application entrypoint.
Creates the app instance, registers all routers, and ensures DB tables exist on startup.
"""

from fastapi import FastAPI
from app.database import Base, engine
import app.models  # noqa: F401 — must import models so they register with Base.metadata

from app.routes import prompts

# Create all tables that don't exist yet — safe to call on every startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Promptory",
    description="Self-hosted prompt version control",
    version="0.1.0",
)

# Register routers — each adds its group of routes to the app
app.include_router(prompts.router)
