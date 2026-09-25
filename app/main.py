"""
Ponto de entrada principal da API REST do Residencial Aurora.
Configura a aplicação FastAPI, lifespan, middlewares e routers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.auditoria import router as router_auditoria
from app.api.routers.sessoes import router as router_sessoes
from app.config import settings
from app.database import async_init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Inicialização segura do banco de dados na subida da aplicação."""
    await async_init_db()
    yield


app = FastAPI(
    title="Residencial Aurora - Assistente Virtual",
    description="API REST padronizada para atendimento a moradores com Google ADK.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_sessoes)
app.include_router(router_auditoria)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": "Residencial Aurora", "version": "1.0.0"}
