"""
Ferramentas do Especialista em Portaria e Visitantes (Garantias 1 e 2).
Toda liberação de acesso na portaria exige confirmação formal e isolamento por unidade.
"""

from __future__ import annotations

from typing import Any, Dict

from google.adk.tools import ToolContext

from app.domain.services import (
    criar_confirmacao_pendente,
    listar_visitantes_apartamento,
)


def solicitar_autorizacao_visitante(
    nome: str, data: str, tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Registra a solicitação de liberação de um visitante na portaria do Residencial Aurora.
    Gera obrigatoriamente uma confirmação pendente de liberação de portaria (Garantia 1).
    A liberação real na portaria só ocorre após o recebimento explícito de confirmação.
    
    Args:
        nome: Nome completo do visitante a ser liberado na portaria.
        data: Data da visita no formato AAAA-MM-DD (ex: '2030-03-25').
    """
    apartamento = tool_context.state.get("apartamento", "")
    session_id = tool_context.session.id if tool_context.session else ""

    conf = criar_confirmacao_pendente(
        session_id=session_id,
        apartamento=apartamento,
        acao="autorizar_visitante",
        detalhes={"nome": nome.strip(), "data": data.strip()},
    )

    return {
        "status": "pendente_confirmacao",
        "confirmacao_id": conf.id,
        "mensagem": (
            f"Solicitação de liberação para o visitante '{nome}' na data {data} registrada. "
            "Para efetivar a liberação na portaria, confirme a solicitação no aplicativo."
        ),
    }


def listar_meus_visitantes(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Lista todos os visitantes autorizados pelo apartamento do morador logado.
    Garante que visitantes de outras unidades jamais sejam expostos (Garantia 2).
    """
    apartamento = tool_context.state.get("apartamento", "")
    visitantes = listar_visitantes_apartamento(apartamento)
    return {
        "apartamento": apartamento,
        "total": len(visitantes),
        "visitantes": visitantes,
    }
