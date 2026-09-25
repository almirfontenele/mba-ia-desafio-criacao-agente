"""
Modelos e esquemas Pydantic estritos para os contratos da API REST do Residencial Aurora.
Atende estritamente às especificações de docs/SPEC.md (Seção 6).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schemas de Sessão e Mensagens (/sessoes)
# ---------------------------------------------------------------------------

class CriarSessaoRequest(BaseModel):
    apartamento: str = Field(..., description="Número da unidade residencial", examples=["101"])


class CriarSessaoResponse(BaseModel):
    session_id: str = Field(..., description="UUID identificador da sessão criada")


class MensagemRequest(BaseModel):
    texto: str = Field(..., description="Mensagem conversacional do morador", examples=["Quero reservar a quadra"])


class ItemConfirmacaoPendente(BaseModel):
    id: str = Field(..., description="Identificador único da confirmação (ex: conf_7c8d9e)")
    acao: str = Field(..., description="Identificador da ação pendente ('reservar_area' ou 'autorizar_visitante')")
    detalhes: Dict[str, Any] = Field(..., description="Parâmetros estruturados da ação")


class MensagemResponse(BaseModel):
    resposta: str = Field(..., description="Resposta textual gerada pelo assistente")
    confirmacoes_pendentes: List[ItemConfirmacaoPendente] = Field(
        default_factory=list,
        description="Lista de ações aguardando aprovação explícita do morador"
    )


class ResponderConfirmacaoRequest(BaseModel):
    id: str = Field(..., description="Identificador da confirmação pendente")
    confirmado: bool = Field(..., description="True para aprovar a ação, False para rejeitar")


# ---------------------------------------------------------------------------
# Schemas de Auditoria (/apartamentos)
# ---------------------------------------------------------------------------

class ReservaAuditoriaResponse(BaseModel):
    codigo: str = Field(..., description="Código identificador único da reserva (ex: RSV-1377)")
    area: str = Field(..., description="Identificador da área comum reservada (ex: quadra)")
    data: str = Field(..., description="Data da reserva no formato AAAA-MM-DD")


class VisitanteAuditoriaResponse(BaseModel):
    nome: str = Field(..., description="Nome do visitante autorizado")
    data: str = Field(..., description="Data da visita no formato AAAA-MM-DD")
