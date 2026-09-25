"""
Ferramentas do Especialista em Reservas (Garantias 1, 2 e 5).
As ferramentas extraem o apartamento exclusivamente de tool_context.state,
garantindo imunidade total a prompt injection ou spoofing de identidade.
"""

from __future__ import annotations

from typing import Any, Dict

from google.adk.tools import ToolContext

from app.domain.services import (
    cancelar_reserva_propria,
    consultar_disponibilidade_area,
    criar_confirmacao_pendente,
    criar_reserva_atomica,
    listar_reservas_apartamento,
    obter_area,
)


def checar_disponibilidade(area: str, data: str) -> Dict[str, Any]:
    """
    Consulta se uma determinada área comum está disponível em uma data específica.
    Consulta neutra: informa apenas se está livre ou ocupada, sem revelar dados de quem reservou.
    
    Args:
        area: Nome ou identificador da área (ex: 'quadra', 'salao-de-festas', 'churrasqueira').
        data: Data pretendida no formato AAAA-MM-DD (ex: '2030-04-20').
    """
    area_obj = obter_area(area)
    area_id = area_obj.id if area_obj else area.lower().strip()
    area_nome = area_obj.nome if area_obj else area

    disponivel = consultar_disponibilidade_area(area_id, data)
    status_txt = "livre para reserva" if disponivel else "já ocupada nesta data"
    return {
        "disponivel": disponivel,
        "area": area_nome,
        "data": data,
        "mensagem": f"A área '{area_nome}' está {status_txt} em {data}.",
    }


def solicitar_reserva(
    area: str, data: str, tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Inicia o procedimento de reserva de uma área comum para a data informada.
    Se a área possuir taxa > 0 (como salão de festas ou churrasqueira), gera obrigatoriamente
    uma confirmação pendente para aprovação do morador.
    Se a área for gratuita (taxa == 0, como a quadra), a reserva é gravada imediatamente.
    
    Args:
        area: Nome ou identificador da área (ex: 'quadra', 'salao-de-festas', 'churrasqueira').
        data: Data pretendida no formato AAAA-MM-DD (ex: '2030-04-20').
    """
    apartamento = tool_context.state.get("apartamento", "")
    session_id = tool_context.session.id if tool_context.session else ""

    area_obj = obter_area(area)
    if not area_obj:
        return {
            "sucesso": False,
            "mensagem": f"Área '{area}' não encontrada no Residencial Aurora.",
        }

    # Garantia 1: taxa > 0 requer confirmação prévia
    if area_obj.requer_confirmacao:
        conf = criar_confirmacao_pendente(
            session_id=session_id,
            apartamento=apartamento,
            acao="reservar_area",
            detalhes={"area": area_obj.id, "data": data.strip()},
        )
        return {
            "status": "pendente_confirmacao",
            "confirmacao_id": conf.id,
            "taxa": area_obj.taxa,
            "mensagem": (
                f"Identifiquei que a reserva do {area_obj.nome} para a data {data} "
                f"possui taxa de cobrança de R$ {area_obj.taxa:.2f}. "
                "Solicitei a confirmação formal no aplicativo para efetivar a reserva."
            ),
        }

    # Taxa zero: grava imediatamente com concorrência atômica (Garantia 5)
    sucesso, codigo, msg = criar_reserva_atomica(
        apartamento=apartamento,
        area_id=area_obj.id,
        data=data.strip(),
    )
    return {
        "status": "concluida" if sucesso else "recusada",
        "sucesso": sucesso,
        "codigo": codigo,
        "mensagem": msg,
    }


def cancelar_minha_reserva(
    identificador: str, tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Cancela uma reserva pertencente exclusivamente ao apartamento do morador logado.
    Não requer confirmação pendente.
    
    Args:
        identificador: Código da reserva (ex: 'RSV-1377') ou a data da reserva (AAAA-MM-DD).
    """
    apartamento = tool_context.state.get("apartamento", "")
    sucesso, msg = cancelar_reserva_propria(apartamento, identificador)
    return {
        "sucesso": sucesso,
        "mensagem": msg,
    }


def listar_minhas_reservas(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Lista todas as reservas ativas da unidade do morador logado.
    Garante que nenhuma informação de outras unidades seja exposta.
    """
    apartamento = tool_context.state.get("apartamento", "")
    reservas = listar_reservas_apartamento(apartamento)
    return {
        "apartamento": apartamento,
        "total": len(reservas),
        "reservas": reservas,
    }
