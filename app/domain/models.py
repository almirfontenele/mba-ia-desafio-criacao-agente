"""
Modelos de domínio do Residencial Aurora.
Entidades puras desacopladas de frameworks externos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Apartamento:
    numero: str
    morador: str


@dataclass
class AreaComum:
    id: str
    nome: str
    taxa: float = 0.0

    @property
    def requer_confirmacao(self) -> bool:
        """Garantia 1: taxa > 0 exige confirmação financeira obrigatória."""
        return self.taxa > 0.0


@dataclass
class Reserva:
    codigo: str
    apartamento: str
    area: str
    data: str  # Formato AAAA-MM-DD
    status: str = "ATIVA"  # "ATIVA" ou "CANCELADA"
    criada_em: Optional[datetime] = None


@dataclass
class Visitante:
    apartamento: str
    nome: str
    data: str  # Formato AAAA-MM-DD
    id: Optional[int] = None
    criado_em: Optional[datetime] = None


@dataclass
class ConfirmacaoPendente:
    id: str
    session_id: str
    apartamento: str
    acao: str  # "reservar_area" ou "autorizar_visitante"
    detalhes: Dict[str, Any]
    status: str = "PENDENTE"  # "PENDENTE", "APROVADA", "NEGADA"
    criada_em: Optional[datetime] = None
    respondida_em: Optional[datetime] = None
