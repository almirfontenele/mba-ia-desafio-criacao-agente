"""
Serviços determinísticos de domínio do Residencial Aurora.
Implementa as regras de negócio das Garantias 1, 2 e 5:
- Isolamento estrito de consultas e ações por apartamento;
- Consulta neutra de disponibilidade;
- Cancelamento exclusivo da própria unidade;
- Concorrência atômica via BEGIN IMMEDIATE e índice de unicidade;
- Máquina de estados de confirmações com validação de idempotência.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import aiosqlite

from app.database import (
    async_immediate_transaction,
    get_async_db_connection,
    get_db_connection,
    immediate_transaction,
)
from app.domain.models import AreaComum, ConfirmacaoPendente


def gerar_codigo_reserva(conn: Optional[sqlite3.Connection] = None) -> str:
    """Gera um código único de reserva (ex.: RSV-8492) nunca reutilizado."""
    while True:
        num = secrets.randbelow(9000) + 1000
        codigo = f"RSV-{num}"
        if conn:
            cur = conn.execute("SELECT 1 FROM reservas WHERE codigo = ?", (codigo,))
            if not cur.fetchone():
                return codigo
        else:
            with get_db_connection() as c:
                cur = c.execute("SELECT 1 FROM reservas WHERE codigo = ?", (codigo,))
                if not cur.fetchone():
                    return codigo


def gerar_id_confirmacao() -> str:
    """Gera um ID único e legível para confirmações pendentes (ex.: conf_a1b2c3d4)."""
    return f"conf_{secrets.token_hex(4)}"


# ---------------------------------------------------------------------------
# Consultas de Auditoria e Isolamento de Apartamento (Garantia 2)
# ---------------------------------------------------------------------------

def listar_reservas_apartamento(
    apartamento: str, db_path: Optional[Union[Path, str]] = None
) -> List[Dict[str, str]]:
    """
    Retorna apenas as reservas ATIVAS do apartamento informado.
    Nunca expõe reservas de outros moradores (Garantia 2).
    """
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT codigo, area, data FROM reservas WHERE apartamento = ? AND status = 'ATIVA' ORDER BY data ASC",
            (str(apartamento),),
        )
        return [
            {"codigo": row["codigo"], "area": row["area"], "data": row["data"]}
            for row in cur.fetchall()
        ]


async def async_listar_reservas_apartamento(
    apartamento: str, db_path: Optional[Union[Path, str]] = None
) -> List[Dict[str, str]]:
    """Versão assíncrona de listar_reservas_apartamento."""
    async with get_async_db_connection(db_path) as conn:
        cur = await conn.execute(
            "SELECT codigo, area, data FROM reservas WHERE apartamento = ? AND status = 'ATIVA' ORDER BY data ASC",
            (str(apartamento),),
        )
        rows = await cur.fetchall()
        return [
            {"codigo": row["codigo"], "area": row["area"], "data": row["data"]}
            for row in rows
        ]


def listar_visitantes_apartamento(
    apartamento: str, db_path: Optional[Union[Path, str]] = None
) -> List[Dict[str, str]]:
    """
    Retorna a lista de visitantes autorizados pelo apartamento informado.
    Isolamento estrito por unidade (Garantia 2).
    """
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT nome, data FROM visitantes WHERE apartamento = ? ORDER BY data ASC, nome ASC",
            (str(apartamento),),
        )
        return [
            {"nome": row["nome"], "data": row["data"]}
            for row in cur.fetchall()
        ]


async def async_listar_visitantes_apartamento(
    apartamento: str, db_path: Optional[Union[Path, str]] = None
) -> List[Dict[str, str]]:
    """Versão assíncrona de listar_visitantes_apartamento."""
    async with get_async_db_connection(db_path) as conn:
        cur = await conn.execute(
            "SELECT nome, data FROM visitantes WHERE apartamento = ? ORDER BY data ASC, nome ASC",
            (str(apartamento),),
        )
        rows = await cur.fetchall()
        return [
            {"nome": row["nome"], "data": row["data"]}
            for row in rows
        ]


def consultar_disponibilidade_area(
    area: str, data: str, db_path: Optional[Union[Path, str]] = None
) -> bool:
    """
    Consulta neutra de disponibilidade (Garantia 2).
    Retorna True se a data estiver livre, False se estiver ocupada.
    Nunca revela quem reservou ou detalhes de terceiros.
    """
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM reservas WHERE area = ? AND data = ? AND status = 'ATIVA'",
            (area.lower().strip(), data.strip()),
        )
        count = cur.fetchone()[0]
        return count == 0


async def async_consultar_disponibilidade_area(
    area: str, data: str, db_path: Optional[Union[Path, str]] = None
) -> bool:
    """Versão assíncrona de consulta neutra de disponibilidade."""
    async with get_async_db_connection(db_path) as conn:
        cur = await conn.execute(
            "SELECT COUNT(*) FROM reservas WHERE area = ? AND data = ? AND status = 'ATIVA'",
            (area.lower().strip(), data.strip()),
        )
        row = await cur.fetchone()
        return row[0] == 0


def cancelar_reserva_propria(
    apartamento: str, identificador: str, db_path: Optional[Union[Path, str]] = None
) -> Tuple[bool, str]:
    """
    Cancela uma reserva pertencente estritamente à própria unidade (Garantia 2).
    O identificador pode ser o código da reserva, a data ou a área.
    Não requer confirmação pendente (RN04).
    """
    ident_limpo = identificador.strip()
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT codigo, area, data FROM reservas 
            WHERE apartamento = ? AND status = 'ATIVA' 
              AND (codigo = ? OR data = ? OR area = ? OR LOWER(area) = LOWER(?))
            """,
            (str(apartamento), ident_limpo, ident_limpo, ident_limpo, ident_limpo),
        )
        row = cur.fetchone()
        if not row:
            return False, f"Nenhuma reserva ativa encontrada para a unidade {apartamento} com '{identificador}'."

        codigo = row["codigo"]
        with immediate_transaction(conn):
            conn.execute(
                "UPDATE reservas SET status = 'CANCELADA' WHERE codigo = ?",
                (codigo,),
            )
        return True, f"Reserva {codigo} ({row['area']} em {row['data']}) cancelada com sucesso."


async def async_cancelar_reserva_propria(
    apartamento: str, identificador: str, db_path: Optional[Union[Path, str]] = None
) -> Tuple[bool, str]:
    """Versão assíncrona de cancelamento de reserva própria."""
    ident_limpo = identificador.strip()
    async with get_async_db_connection(db_path) as conn:
        cur = await conn.execute(
            """
            SELECT codigo, area, data FROM reservas 
            WHERE apartamento = ? AND status = 'ATIVA' 
              AND (codigo = ? OR data = ? OR area = ? OR LOWER(area) = LOWER(?))
            """,
            (str(apartamento), ident_limpo, ident_limpo, ident_limpo, ident_limpo),
        )
        row = await cur.fetchone()
        if not row:
            return False, f"Nenhuma reserva ativa encontrada para a unidade {apartamento} com '{identificador}'."

        codigo = row["codigo"]
        async with async_immediate_transaction(conn):
            await conn.execute(
                "UPDATE reservas SET status = 'CANCELADA' WHERE codigo = ?",
                (codigo,),
            )
        return True, f"Reserva {codigo} ({row['area']} em {row['data']}) cancelada com sucesso."


# ---------------------------------------------------------------------------
# Concorrência Atômica e Criação de Reserva (Garantia 5)
# ---------------------------------------------------------------------------

def obter_area(
    area_id: str, db_path: Optional[Union[Path, str]] = None
) -> Optional[AreaComum]:
    """Obtém detalhes de uma área comum."""
    area_id_clean = area_id.lower().strip()
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT id, nome, taxa FROM areas WHERE id = ? OR LOWER(nome) = ?",
            (area_id_clean, area_id_clean),
        )
        row = cur.fetchone()
        if row:
            return AreaComum(id=row["id"], nome=row["nome"], taxa=float(row["taxa"]))
        return None


async def async_obter_area(
    area_id: str, db_path: Optional[Union[Path, str]] = None
) -> Optional[AreaComum]:
    """Versão assíncrona de obter_area."""
    area_id_clean = area_id.lower().strip()
    async with get_async_db_connection(db_path) as conn:
        cur = await conn.execute(
            "SELECT id, nome, taxa FROM areas WHERE id = ? OR LOWER(nome) = ?",
            (area_id_clean, area_id_clean),
        )
        row = await cur.fetchone()
        if row:
            return AreaComum(id=row["id"], nome=row["nome"], taxa=float(row["taxa"]))
        return None


def criar_reserva_atomica(
    apartamento: str,
    area_id: str,
    data: str,
    db_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, Optional[str], str]:
    """
    Gravação atômica da reserva com tratamento gracioso de concorrência (Garantia 5).
    Retorna (sucesso, codigo, mensagem).
    Em caso de colisão simultânea, captura sqlite3.IntegrityError e retorna
    status amigável sem crashar a aplicação.
    """
    area = obter_area(area_id, db_path=db_path)
    if not area:
        return False, None, f"Área '{area_id}' não encontrada no condomínio."

    with get_db_connection(db_path) as conn:
        try:
            with immediate_transaction(conn):
                # 1. Verifica disponibilidade dentro da transação imediata
                cur = conn.execute(
                    "SELECT COUNT(*) FROM reservas WHERE area = ? AND data = ? AND status = 'ATIVA'",
                    (area.id, data.strip()),
                )
                if cur.fetchone()[0] > 0:
                    return (
                        False,
                        None,
                        f"A área '{area.nome}' já está reservada para a data {data} por outro morador.",
                    )

                # 2. Gera código único e grava
                codigo = gerar_codigo_reserva(conn)
                conn.execute(
                    """
                    INSERT INTO reservas (codigo, apartamento, area, data, status)
                    VALUES (?, ?, ?, ?, 'ATIVA')
                    """,
                    (codigo, str(apartamento), area.id, data.strip()),
                )
            return True, codigo, f"Reserva {codigo} confirmada com sucesso para {area.nome} em {data}."

        except sqlite3.IntegrityError:
            # Captura colisão de unicidade ou integridade relacional
            return (
                False,
                None,
                f"A área '{area.nome}' acabou de ser reservada para a data {data} por outro morador.",
            )


async def async_criar_reserva_atomica(
    apartamento: str,
    area_id: str,
    data: str,
    db_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, Optional[str], str]:
    """Versão assíncrona de criação atômica de reserva com Garantia 5."""
    area = await async_obter_area(area_id, db_path=db_path)
    if not area:
        return False, None, f"Área '{area_id}' não encontrada no condomínio."

    async with get_async_db_connection(db_path) as conn:
        try:
            async with async_immediate_transaction(conn):
                cur = await conn.execute(
                    "SELECT COUNT(*) FROM reservas WHERE area = ? AND data = ? AND status = 'ATIVA'",
                    (area.id, data.strip()),
                )
                row = await cur.fetchone()
                if row[0] > 0:
                    return (
                        False,
                        None,
                        f"A área '{area.nome}' já está reservada para a data {data} por outro morador.",
                    )

                # Gera código único
                codigo = gerar_codigo_reserva()
                await conn.execute(
                    """
                    INSERT INTO reservas (codigo, apartamento, area, data, status)
                    VALUES (?, ?, ?, ?, 'ATIVA')
                    """,
                    (codigo, str(apartamento), area.id, data.strip()),
                )
            return True, codigo, f"Reserva {codigo} confirmada com sucesso para {area.nome} em {data}."

        except (sqlite3.IntegrityError, aiosqlite.IntegrityError):
            return (
                False,
                None,
                f"A área '{area.nome}' acabou de ser reservada para a data {data} por outro morador.",
            )


def registrar_visitante(
    apartamento: str,
    nome: str,
    data: str,
    db_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, str]:
    """Registra visitante autorizado para a unidade."""
    with get_db_connection(db_path) as conn:
        with immediate_transaction(conn):
            conn.execute(
                "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
                (str(apartamento), nome.strip(), data.strip()),
            )
        return True, f"Visitante {nome} autorizado com sucesso para o dia {data} no apartamento {apartamento}."


async def async_registrar_visitante(
    apartamento: str,
    nome: str,
    data: str,
    db_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, str]:
    """Versão assíncrona de registrar_visitante."""
    async with get_async_db_connection(db_path) as conn:
        async with async_immediate_transaction(conn):
            await conn.execute(
                "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
                (str(apartamento), nome.strip(), data.strip()),
            )
        return True, f"Visitante {nome} autorizado com sucesso para o dia {data} no apartamento {apartamento}."


# ---------------------------------------------------------------------------
# Gestão de Confirmações Pendentes e Idempotência (Garantia 1)
# ---------------------------------------------------------------------------

def criar_confirmacao_pendente(
    session_id: str,
    apartamento: str,
    acao: str,
    detalhes: Dict[str, Any],
    db_path: Optional[Union[Path, str]] = None,
) -> ConfirmacaoPendente:
    """Cria e persiste uma confirmação pendente no banco de dados."""
    conf_id = gerar_id_confirmacao()
    detalhes_json = json.dumps(detalhes, ensure_ascii=False)

    with get_db_connection(db_path) as conn:
        with immediate_transaction(conn):
            conn.execute(
                """
                INSERT INTO confirmacoes (id, session_id, apartamento, acao, detalhes_json, status)
                VALUES (?, ?, ?, ?, ?, 'PENDENTE')
                """,
                (conf_id, str(session_id), str(apartamento), acao, detalhes_json),
            )

    return ConfirmacaoPendente(
        id=conf_id,
        session_id=session_id,
        apartamento=apartamento,
        acao=acao,
        detalhes=detalhes,
        status="PENDENTE",
    )


async def async_criar_confirmacao_pendente(
    session_id: str,
    apartamento: str,
    acao: str,
    detalhes: Dict[str, Any],
    db_path: Optional[Union[Path, str]] = None,
) -> ConfirmacaoPendente:
    """Versão assíncrona de criação de confirmação pendente."""
    conf_id = gerar_id_confirmacao()
    detalhes_json = json.dumps(detalhes, ensure_ascii=False)

    async with get_async_db_connection(db_path) as conn:
        async with async_immediate_transaction(conn):
            await conn.execute(
                """
                INSERT INTO confirmacoes (id, session_id, apartamento, acao, detalhes_json, status)
                VALUES (?, ?, ?, ?, ?, 'PENDENTE')
                """,
                (conf_id, str(session_id), str(apartamento), acao, detalhes_json),
            )

    return ConfirmacaoPendente(
        id=conf_id,
        session_id=session_id,
        apartamento=apartamento,
        acao=acao,
        detalhes=detalhes,
        status="PENDENTE",
    )


def listar_confirmacoes_pendentes(
    session_id: str, db_path: Optional[Union[Path, str]] = None
) -> List[Dict[str, Any]]:
    """Retorna as confirmações atualmente com status PENDENTE para a sessão."""
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT id, acao, detalhes_json FROM confirmacoes 
            WHERE session_id = ? AND status = 'PENDENTE'
            ORDER BY criada_em ASC
            """,
            (str(session_id),),
        )
        pendentes = []
        for row in cur.fetchall():
            pendentes.append({
                "id": row["id"],
                "acao": row["acao"],
                "detalhes": json.loads(row["detalhes_json"]),
            })
        return pendentes


async def async_listar_confirmacoes_pendentes(
    session_id: str, db_path: Optional[Union[Path, str]] = None
) -> List[Dict[str, Any]]:
    """Versão assíncrona de listar_confirmacoes_pendentes."""
    async with get_async_db_connection(db_path) as conn:
        cur = await conn.execute(
            """
            SELECT id, acao, detalhes_json FROM confirmacoes 
            WHERE session_id = ? AND status = 'PENDENTE'
            ORDER BY criada_em ASC
            """,
            (str(session_id),),
        )
        rows = await cur.fetchall()
        pendentes = []
        for row in rows:
            pendentes.append({
                "id": row["id"],
                "acao": row["acao"],
                "detalhes": json.loads(row["detalhes_json"]),
            })
        return pendentes


def responder_confirmacao(
    session_id: str,
    confirmacao_id: str,
    confirmado: bool,
    db_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, str, int]:
    """
    Processa a resposta a uma confirmação com estrita idempotência (Garantia 1).
    Retorna (sucesso, mensagem, status_code).
    - Status 409 Conflict se o ID não existir ou já tiver sido respondido.
    - Status 200 OK quando respondido com sucesso.
    """
    with get_db_connection(db_path) as conn:
        # Busca a confirmação vinculada a esta sessão
        cur = conn.execute(
            "SELECT * FROM confirmacoes WHERE id = ? AND session_id = ?",
            (confirmacao_id.strip(), str(session_id)),
        )
        row = cur.fetchone()
        if not row:
            return False, f"Confirmação '{confirmacao_id}' não encontrada para esta sessão.", 409

        if row["status"] != "PENDENTE":
            return (
                False,
                f"Confirmação '{confirmacao_id}' já foi respondida anteriormente com status '{row['status']}'.",
                409,
            )

        novo_status = "APROVADA" if confirmado else "NEGADA"
        acao = row["acao"]
        apartamento = row["apartamento"]
        detalhes = json.loads(row["detalhes_json"])

        with immediate_transaction(conn):
            conn.execute(
                """
                UPDATE confirmacoes 
                SET status = ?, respondida_em = CURRENT_TIMESTAMP 
                WHERE id = ?
                """,
                (novo_status, confirmacao_id),
            )

        if not confirmado:
            return True, f"Ação de '{acao}' foi cancelada pelo morador.", 200

        # Executa a ação aprovada
        if acao == "reservar_area":
            ok, codigo, msg = criar_reserva_atomica(
                apartamento=apartamento,
                area_id=detalhes.get("area", ""),
                data=detalhes.get("data", ""),
                db_path=db_path,
            )
            return ok, msg, 200

        elif acao == "autorizar_visitante":
            ok, msg = registrar_visitante(
                apartamento=apartamento,
                nome=detalhes.get("nome", ""),
                data=detalhes.get("data", ""),
                db_path=db_path,
            )
            return ok, msg, 200

        return True, f"Ação '{acao}' processada.", 200


async def async_responder_confirmacao(
    session_id: str,
    confirmacao_id: str,
    confirmado: bool,
    db_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, str, int]:
    """Versão assíncrona de responder_confirmacao."""
    async with get_async_db_connection(db_path) as conn:
        cur = await conn.execute(
            "SELECT * FROM confirmacoes WHERE id = ? AND session_id = ?",
            (confirmacao_id.strip(), str(session_id)),
        )
        row = await cur.fetchone()
        if not row:
            return False, f"Confirmação '{confirmacao_id}' não encontrada para esta sessão.", 409

        if row["status"] != "PENDENTE":
            return (
                False,
                f"Confirmação '{confirmacao_id}' já foi respondida anteriormente com status '{row['status']}'.",
                409,
            )

        novo_status = "APROVADA" if confirmado else "NEGADA"
        acao = row["acao"]
        apartamento = row["apartamento"]
        detalhes = json.loads(row["detalhes_json"])

        async with async_immediate_transaction(conn):
            await conn.execute(
                """
                UPDATE confirmacoes 
                SET status = ?, respondida_em = CURRENT_TIMESTAMP 
                WHERE id = ?
                """,
                (novo_status, confirmacao_id),
            )

        if not confirmado:
            return True, f"Ação de '{acao}' foi cancelada pelo morador.", 200

        if acao == "reservar_area":
            ok, codigo, msg = await async_criar_reserva_atomica(
                apartamento=apartamento,
                area_id=detalhes.get("area", ""),
                data=detalhes.get("data", ""),
                db_path=db_path,
            )
            return ok, msg, 200

        elif acao == "autorizar_visitante":
            ok, msg = await async_registrar_visitante(
                apartamento=apartamento,
                nome=detalhes.get("nome", ""),
                data=detalhes.get("data", ""),
                db_path=db_path,
            )
            return ok, msg, 200

        return True, f"Ação '{acao}' processada.", 200
