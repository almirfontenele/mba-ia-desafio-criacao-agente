"""
Testes de integração para as rotas da API REST do Residencial Aurora.
Valida os contratos de entrada e saída definidos em docs/SPEC.md.
"""

import pytest
import httpx
from pathlib import Path

from app.main import app
from app.scripts.restore_data import restore_initial_data


@pytest.fixture(autouse=True)
def setup_db():
    """Garante banco de dados restaurado antes dos testes de API."""
    restore_initial_data()


@pytest.mark.asyncio
async def test_api_criar_sessao_e_consultar_auditoria():
    """Valida rotas /sessoes (201) e rotas de auditoria (200)."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Cria sessão para o 101
        res = await client.post("/sessoes", json={"apartamento": "101"})
        assert res.status_code == 201
        body = res.json()
        assert "session_id" in body
        sid = body["session_id"]

        # 2. Consulta reservas do 101
        res_r = await client.get("/apartamentos/101/reservas")
        assert res_r.status_code == 200
        reservas = res_r.json()
        assert len(reservas) == 1
        assert reservas[0]["codigo"] == "RSV-1377"

        # 3. Consulta visitantes do 302
        res_v = await client.get("/apartamentos/302/visitantes")
        assert res_v.status_code == 200
        visitantes = res_v.json()
        assert len(visitantes) == 1
        assert visitantes[0]["nome"] == "Marina Duarte"


@pytest.mark.asyncio
async def test_api_confirmacao_idempotencia_409():
    """Valida status 409 Conflict para ID inválido de confirmação."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/sessoes", json={"apartamento": "201"})
        sid = res.json()["session_id"]

        # Confirmação com ID inexistente deve retornar 409
        res_conf = await client.post(
            f"/sessoes/{sid}/confirmacoes",
            json={"id": "conf_fantasma", "confirmado": True},
        )
        assert res_conf.status_code == 409


@pytest.mark.asyncio
async def test_api_eventos_sessao_e_404():
    """Valida GET /sessoes/{session_id}/eventos e retorno 404 para sessão inexistente."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Sessão existente
        res = await client.post("/sessoes", json={"apartamento": "102"})
        sid = res.json()["session_id"]

        res_ev = await client.get(f"/sessoes/{sid}/eventos")
        assert res_ev.status_code == 200
        assert isinstance(res_ev.json(), list)

        # Sessão inexistente deve dar 404
        res_404 = await client.get("/sessoes/uuid-nao-existe/eventos")
        assert res_404.status_code == 404
