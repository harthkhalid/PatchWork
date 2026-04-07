"""Patchwork FastAPI application."""

import logging
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import redis.asyncio as redis

from app.config import get_settings
from app.database import async_session_maker, init_db
from app.models import StarCounter
from sqlalchemy import select

from app.routers import api, webhooks

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    async with async_session_maker() as session:
        row = await session.scalar(select(StarCounter).where(StarCounter.id == 1))
        if not row:
            session.add(StarCounter(id=1, stars=512))
            await session.commit()
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    yield
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(webhooks.router)
    app.include_router(api.router)

    @app.get("/install")
    async def install_github_app():
        slug = settings.github_app_slug
        url = f"https://github.com/apps/{quote(slug)}/installations/new"
        return RedirectResponse(url, status_code=302)

    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "docs": "/docs",
            "install": "/install",
            "dashboard": settings.public_base_url.rstrip("/") + "/",
        }

    return app


app = create_app()
