"""
Rotas de Auditoria e Verificação (/apartamentos).
Utilizadas pelo avaliador para conferir alterações de estado sem passar pelo LLM.
- GET /apartamentos/{numero}/reservas
- GET /apartamentos/{numero}/visitantes
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, status

from app.api.schemas import ReservaAuditoriaResponse, VisitanteAuditoriaResponse
from app.domain.services import (
    async_listar_reservas_apartamento,
    async_listar_visitantes_apartamento,
)

router = APIRouter(prefix="/apartamentos", tags=["Auditoria"])


@router.get(
    "/{numero}/reservas",
    response_model=List[ReservaAuditoriaResponse],
    status_code=status.HTTP_200_OK,
    summary="Lista reservas ativas da unidade para auditoria",
)
async def obter_reservas_apartamento(numero: str) -> List[ReservaAuditoriaResponse]:
    """Retorna a lista de reservas ativas de um apartamento."""
    reservas = await async_listar_reservas_apartamento(numero)
    return [
        ReservaAuditoriaResponse(
            codigo=r["codigo"],
            area=r["area"],
            data=r["data"],
        )
        for r in reservas
    ]


@router.get(
    "/{numero}/visitantes",
    response_model=List[VisitanteAuditoriaResponse],
    status_code=status.HTTP_200_OK,
    summary="Lista visitantes autorizados da unidade para auditoria",
)
async def obter_visitantes_apartamento(numero: str) -> List[VisitanteAuditoriaResponse]:
    """Retorna a lista de visitantes autorizados para um apartamento."""
    visitantes = await async_listar_visitantes_apartamento(numero)
    return [
        VisitanteAuditoriaResponse(
            nome=v["nome"],
            data=v["data"],
        )
        for v in visitantes
    ]
