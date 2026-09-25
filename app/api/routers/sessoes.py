"""
Router de Sessões da API REST (/sessoes).
Endpoints:
- POST /sessoes: Inicializa sessão para um apartamento;
- POST /sessoes/{session_id}/mensagens: Envia mensagem e executa turno conversacional no ADK;
- POST /sessoes/{session_id}/confirmacoes: Responde a confirmação com validação de idempotência (409);
- GET /sessoes/{session_id}/eventos: Retorna o histórico integral de eventos da sessão (404 se inexistente).
"""

from __future__ import annotations

from typing import Any, List
from fastapi import APIRouter, HTTPException, status

from app.agents.runtime import (
    criar_sessao_adk,
    executar_turno_mensagem,
    obter_eventos_sessao,
    obter_sessao_adk,
)
from app.api.schemas import (
    CriarSessaoRequest,
    CriarSessaoResponse,
    ItemConfirmacaoPendente,
    MensagemRequest,
    MensagemResponse,
    ResponderConfirmacaoRequest,
)
from app.domain.services import (
    async_listar_confirmacoes_pendentes,
    async_responder_confirmacao,
)

router = APIRouter(prefix="/sessoes", tags=["Sessões"])


@router.post(
    "",
    response_model=CriarSessaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma nova sessão conversacional vinculada a um apartamento",
)
async def criar_sessao(payload: CriarSessaoRequest) -> CriarSessaoResponse:
    """Garantia 2: o apartamento é injetado no estado da sessão de forma definitiva."""
    sessao = await criar_sessao_adk(apartamento=payload.apartamento)
    return CriarSessaoResponse(session_id=sessao.id)


@router.post(
    "/{session_id}/mensagens",
    response_model=MensagemResponse,
    status_code=status.HTTP_200_OK,
    summary="Envia mensagem conversacional do morador",
)
async def enviar_mensagem(
    session_id: str,
    payload: MensagemRequest,
) -> MensagemResponse:
    """Executa o fluxo do agente e retorna resposta textual e confirmações pendentes."""
    sessao = await obter_sessao_adk(session_id)
    if not sessao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_id}' não encontrada.",
        )

    try:
        texto_resposta, pendentes = await executar_turno_mensagem(
            session_id=session_id,
            texto_usuario=payload.texto,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante execução da mensagem: {e}",
        )

    itens_pendentes = [
        ItemConfirmacaoPendente(
            id=item["id"],
            acao=item["acao"],
            detalhes=item["detalhes"],
        )
        for item in pendentes
    ]

    return MensagemResponse(
        resposta=texto_resposta or "Solicitação processada.",
        confirmacoes_pendentes=itens_pendentes,
    )


@router.post(
    "/{session_id}/confirmacoes",
    response_model=MensagemResponse,
    status_code=status.HTTP_200_OK,
    summary="Aprova ou rejeita uma ação pendente (Garantia 1)",
)
async def responder_confirmacao_endpoint(
    session_id: str,
    payload: ResponderConfirmacaoRequest,
) -> MensagemResponse:
    """
    Processa a resposta a uma confirmação pendente.
    Idempotência estrita: retorna 409 Conflict se o ID não existir ou já tiver sido respondido.
    """
    sessao = await obter_sessao_adk(session_id)
    if not sessao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_id}' não encontrada.",
        )

    ok, msg, code = await async_responder_confirmacao(
        session_id=session_id,
        confirmacao_id=payload.id,
        confirmado=payload.confirmado,
    )

    if code == 409:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=msg,
        )

    pendentes = await async_listar_confirmacoes_pendentes(session_id)
    itens_pendentes = [
        ItemConfirmacaoPendente(
            id=item["id"],
            acao=item["acao"],
            detalhes=item["detalhes"],
        )
        for item in pendentes
    ]

    return MensagemResponse(
        resposta=msg,
        confirmacoes_pendentes=itens_pendentes,
    )


@router.get(
    "/{session_id}/eventos",
    response_model=List[Any],
    status_code=status.HTTP_200_OK,
    summary="Recupera histórico cronológico de eventos gravados da sessão",
)
async def obter_eventos_endpoint(session_id: str) -> List[Any]:
    """Retorna os eventos da sessão gravados no SQLite do ADK (404 se inexistente)."""
    eventos = await obter_eventos_sessao(session_id)
    if eventos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_id}' não encontrada.",
        )
    return eventos
