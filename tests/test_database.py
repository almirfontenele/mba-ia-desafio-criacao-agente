"""
Testes unitários e de integração para app/database.py.
Valida persistência SQLite, modo WAL, chaves estrangeiras e índice de unicidade (Garantia 5).
"""

import sqlite3
import pytest
import aiosqlite
from pathlib import Path

from app.database import (
    init_db,
    async_init_db,
    get_db_connection,
    get_async_db_connection,
    immediate_transaction,
    async_immediate_transaction,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Retorna um caminho temporário para arquivo de banco de dados."""
    return tmp_path / "test_aurora.db"


def test_init_db_creates_tables_and_pragmas(temp_db_path: Path):
    """Testa a criação de tabelas e ativação de PRAGMAs (WAL e Foreign Keys)."""
    init_db(temp_db_path)

    with get_db_connection(temp_db_path) as conn:
        # 1. Verifica PRAGMA journal_mode
        cur = conn.execute("PRAGMA journal_mode;")
        journal_mode = cur.fetchone()[0]
        assert journal_mode.lower() == "wal", f"Esperado WAL, obtido {journal_mode}"

        # 2. Verifica PRAGMA foreign_keys
        cur = conn.execute("PRAGMA foreign_keys;")
        foreign_keys = cur.fetchone()[0]
        assert foreign_keys == 1, "Chaves estrangeiras não estão ativadas"

        # 3. Verifica existência de todas as 5 tabelas
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = {row[0] for row in cur.fetchall()}
        expected_tables = {"apartamentos", "areas", "reservas", "visitantes", "confirmacoes"}
        assert expected_tables.issubset(tables), f"Tabelas ausentes: {expected_tables - tables}"

        # 4. Verifica existência do índice de unicidade parcial
        cur = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND name='uq_reservas_area_data_ativa';"
        )
        row = cur.fetchone()
        assert row is not None, "Índice uq_reservas_area_data_ativa não foi criado"
        assert "WHERE status = 'ATIVA'" in row["sql"], "Cláusula WHERE status = 'ATIVA' ausente no índice"


def test_foreign_key_enforcement(temp_db_path: Path):
    """Testa se as chaves estrangeiras impedem inserções inválidas."""
    init_db(temp_db_path)

    with get_db_connection(temp_db_path) as conn:
        # Inserção de reserva para apartamento inexistente deve falhar
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, ?)",
                ("RSV-9999", "999", "quadra", "2030-01-01", "ATIVA"),
            )


def test_unique_index_garantia_5(temp_db_path: Path):
    """
    Testa o índice de unicidade (Garantia 5):
    Dois moradores não podem reservar a mesma área na mesma data com status 'ATIVA'.
    """
    init_db(temp_db_path)

    with get_db_connection(temp_db_path) as conn:
        # Insere dados de base
        conn.execute("INSERT INTO apartamentos (numero, morador) VALUES ('101', 'Morador 101')")
        conn.execute("INSERT INTO apartamentos (numero, morador) VALUES ('201', 'Morador 201')")
        conn.execute("INSERT INTO areas (id, nome, taxa) VALUES ('salao-de-festas', 'Salão de Festas', 150.0)")

        # 1ª reserva ativa: deve funcionar
        conn.execute(
            "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, ?)",
            ("RSV-1001", "101", "salao-de-festas", "2030-05-11", "ATIVA"),
        )

        # 2ª reserva ativa para mesma área e data: deve lançar sqlite3.IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, ?)",
                ("RSV-1002", "201", "salao-de-festas", "2030-05-11", "ATIVA"),
            )

        # Se a primeira reserva for cancelada, nova reserva ativa na mesma data deve ser permitida
        conn.execute("UPDATE reservas SET status = 'CANCELADA' WHERE codigo = 'RSV-1001'")

        conn.execute(
            "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, ?)",
            ("RSV-1002", "201", "salao-de-festas", "2030-05-11", "ATIVA"),
        )
        
        cur = conn.execute("SELECT COUNT(*) FROM reservas WHERE area = 'salao-de-festas' AND data = '2030-05-11'")
        assert cur.fetchone()[0] == 2  # 1 cancelada + 1 ativa


def test_immediate_transaction(temp_db_path: Path):
    """Testa gerenciamento de transação atômica BEGIN IMMEDIATE."""
    init_db(temp_db_path)

    with get_db_connection(temp_db_path) as conn:
        conn.execute("INSERT INTO apartamentos (numero, morador) VALUES ('101', 'Helena')")

        with immediate_transaction(conn):
            conn.execute("UPDATE apartamentos SET morador = 'Helena Silva' WHERE numero = '101'")

        cur = conn.execute("SELECT morador FROM apartamentos WHERE numero = '101'")
        assert cur.fetchone()["morador"] == "Helena Silva"

        # Testa rollback em caso de erro
        with pytest.raises(ValueError):
            with immediate_transaction(conn):
                conn.execute("UPDATE apartamentos SET morador = 'Nome Cancelado' WHERE numero = '101'")
                raise ValueError("Simulação de falha")

        cur = conn.execute("SELECT morador FROM apartamentos WHERE numero = '101'")
        assert cur.fetchone()["morador"] == "Helena Silva"


@pytest.mark.asyncio
async def test_async_database_operations(temp_db_path: Path):
    """Testa inicialização e transações assíncronas via aiosqlite."""
    await async_init_db(temp_db_path)

    async with get_async_db_connection(temp_db_path) as conn:
        # Verifica PRAGMA foreign_keys
        cur = await conn.execute("PRAGMA foreign_keys;")
        row = await cur.fetchone()
        assert row[0] == 1

        # Insere dados usando async_immediate_transaction
        async with async_immediate_transaction(conn):
            await conn.execute("INSERT INTO apartamentos (numero, morador) VALUES ('301', 'Cecília')")

        cur = await conn.execute("SELECT morador FROM apartamentos WHERE numero = '301'")
        row = await cur.fetchone()
        assert row["morador"] == "Cecília"
