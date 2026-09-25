"""
Módulo de Banco de Dados Relacional SQLite para o Residencial Aurora.
Suporta persistência durável em disco (aurora.db), WAL mode, chaves estrangeiras,
transações atômicas BEGIN IMMEDIATE e índice de unicidade para reservas ativas.
"""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional, Union

import aiosqlite

from app.config import settings

# Esquema DDL oficial conforme especificado em docs/SPEC.md (Seção 5)
DDL_SCHEMA = """
-- Habilitar integridade referencial e WAL mode
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 1. Unidades Residenciais (Semente imutável de apartamentos.json)
CREATE TABLE IF NOT EXISTS apartamentos (
    numero TEXT PRIMARY KEY,
    morador TEXT NOT NULL
);

-- 2. Áreas Comuns (Semente imutável de areas.json)
CREATE TABLE IF NOT EXISTS areas (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    taxa REAL NOT NULL DEFAULT 0.0
);

-- 3. Reservas do Condomínio
CREATE TABLE IF NOT EXISTS reservas (
    codigo TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL,
    area TEXT NOT NULL,
    data TEXT NOT NULL, -- Formato AAAA-MM-DD
    status TEXT NOT NULL DEFAULT 'ATIVA', -- 'ATIVA', 'CANCELADA'
    criada_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (apartamento) REFERENCES apartamentos(numero),
    FOREIGN KEY (area) REFERENCES areas(id)
);

-- Índice de Unicidade: Garantia 5 (Apenas uma reserva ATIVA por área e data)
CREATE UNIQUE INDEX IF NOT EXISTS uq_reservas_area_data_ativa 
ON reservas(area, data) 
WHERE status = 'ATIVA';

-- Índice para busca rápida de reservas por morador (Garantia 2)
CREATE INDEX IF NOT EXISTS idx_reservas_apartamento ON reservas(apartamento);

-- 4. Visitantes Autorizados
CREATE TABLE IF NOT EXISTS visitantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartamento TEXT NOT NULL,
    nome TEXT NOT NULL,
    data TEXT NOT NULL, -- Formato AAAA-MM-DD
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (apartamento) REFERENCES apartamentos(numero)
);

CREATE INDEX IF NOT EXISTS idx_visitantes_apartamento ON visitantes(apartamento);

-- 5. Confirmações Pendentes e Histórico (Garantia 1)
CREATE TABLE IF NOT EXISTS confirmacoes (
    id TEXT PRIMARY KEY, -- ex: conf_7c8d9e
    session_id TEXT NOT NULL,
    apartamento TEXT NOT NULL,
    acao TEXT NOT NULL, -- 'reservar_area', 'autorizar_visitante'
    detalhes_json TEXT NOT NULL, -- {"area": "...", "data": "..."} ou {"nome": "...", "data": "..."}
    status TEXT NOT NULL DEFAULT 'PENDENTE', -- 'PENDENTE', 'APROVADA', 'NEGADA'
    criada_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    respondida_em DATETIME NULL
);

CREATE INDEX IF NOT EXISTS idx_confirmacoes_session ON confirmacoes(session_id, status);
"""


def get_db_path(db_path: Optional[Union[Path, str]] = None) -> Path:
    """Retorna o caminho do arquivo SQLite a ser utilizado."""
    if db_path is not None:
        p = Path(db_path)
        if not p.is_absolute() and str(p) != ":memory:":
            return settings.database_file_path.parent / p
        return p
    return settings.database_file_path


@contextmanager
def get_db_connection(
    db_path: Optional[Union[Path, str]] = None,
) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager síncrono para obter conexão SQLite com PRAGMAs configurados
    e suporte a acesso a colunas por nome (Row).
    """
    path = get_db_path(db_path)
    conn = sqlite3.connect(
        str(path),
        timeout=15.0,
        autocommit=True,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def get_async_db_connection(
    db_path: Optional[Union[Path, str]] = None,
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Context manager assíncrono para conexão com SQLite utilizando aiosqlite.
    Garante foreign_keys=ON e WAL mode.
    """
    path = get_db_path(db_path)
    conn = await aiosqlite.connect(
        str(path),
        timeout=15.0,
        autocommit=True,
    )
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON;")
    if str(path) != ":memory:":
        await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        yield conn
    finally:
        await conn.close()


@contextmanager
def immediate_transaction(
    conn: sqlite3.Connection,
) -> Generator[sqlite3.Connection, None, None]:
    """
    Gerencia uma transação atômica BEGIN IMMEDIATE em SQLite síncrono.
    Garante o bloqueio exclusivo de escrita na abertura da transação (Garantia 5).
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


@asynccontextmanager
async def async_immediate_transaction(
    conn: aiosqlite.Connection,
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Gerencia uma transação atômica BEGIN IMMEDIATE em SQLite assíncrono.
    Garante o bloqueio exclusivo de escrita na abertura da transação (Garantia 5).
    """
    await conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        await conn.execute("COMMIT")
    except Exception:
        await conn.execute("ROLLBACK")
        raise


def init_db(db_path: Optional[Union[Path, str]] = None) -> None:
    """
    Inicializa o banco de dados aplicando o esquema DDL completo e criando os índices necessários.
    """
    path = get_db_path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    with get_db_connection(path) as conn:
        conn.executescript(DDL_SCHEMA)


async def async_init_db(db_path: Optional[Union[Path, str]] = None) -> None:
    """
    Inicializa o banco de dados de forma assíncrona aplicando o DDL.
    """
    path = get_db_path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    async with get_async_db_connection(path) as conn:
        await conn.executescript(DDL_SCHEMA)


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Dependência do FastAPI para injeção de conexão SQLite assíncrona por request.
    """
    async with get_async_db_connection() as conn:
        yield conn
