"""
Configuração do pytest e fixtures para a bateria de testes do Residencial Aurora.
"""

from typing import AsyncGenerator
import pytest
import pytest_asyncio
import httpx

from app.main import app
from app.scripts.restore_data import restore_initial_data


@pytest.fixture(autouse=True)
def restaurar_banco_antes_de_cada_teste():
    """Restaura o banco SQLite para o estado original antes de cada teste."""
    restore_initial_data()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Cliente HTTP assíncrono conectado diretamente à aplicação FastAPI."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost:8000",
    ) as ac:
        yield ac
