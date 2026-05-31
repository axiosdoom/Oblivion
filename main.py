from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import init_db
    init_db()
    logging.getLogger(__name__).info("Database initialized")
    yield


app = FastAPI(title="Oblivion Bond Analyzer", lifespan=lifespan)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="app/static"), name="static")

from app.routes.api import router as api_router
from app.routes.pages import router as pages_router

app.include_router(api_router)
app.include_router(pages_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)