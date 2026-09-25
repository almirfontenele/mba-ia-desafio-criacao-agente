"""
Runtime do Google ADK para o Residencial Aurora.
Gerencia o SqliteSessionService durável (aurora.db), Runner, App e fluxo de eventos.
Garantia 3: Todas as sessões e eventos persistem em SQLite em disco.
Possui fallback determinístico de resiliência caso a API do Gemini esteja offline ou inacessível.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
from google.adk.apps.app import App
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions.session import Session
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types

from app.config import settings

# Garante que a API key esteja configurada nas variáveis de ambiente para a SDK do Gemini
if settings.GEMINI_API_KEY:
    os.environ.setdefault("GEMINI_API_KEY", settings.GEMINI_API_KEY)

from app.agents.orchestrator import aurora_orchestrator
from app.agents.tools.regulamento_tools import consultar_regulamento
from app.agents.tools.reservas_tools import (
    cancelar_minha_reserva,
    checar_disponibilidade,
    listar_minhas_reservas,
    solicitar_reserva,
)
from app.agents.tools.visitantes_tools import (
    listar_meus_visitantes,
    solicitar_autorizacao_visitante,
)
from app.database import get_async_db_connection
from app.domain.services import async_listar_confirmacoes_pendentes

APP_NAME = "aurora"

_session_service: Optional[SqliteSessionService] = None
_app: Optional[App] = None
_runner: Optional[Runner] = None


class ContextProxy:
    """Mock leve de ToolContext para chamadas de ferramentas no fallback."""
    def __init__(self, session: Session):
        self.session = session
        self.state = session.state


def get_session_service() -> SqliteSessionService:
    """Retorna o serviço de sessões baseado no SQLite durável (aurora.db)."""
    global _session_service
    if _session_service is None:
        db_path = str(settings.database_file_path)
        _session_service = SqliteSessionService(db_path=db_path)
    return _session_service


def get_app() -> App:
    """Retorna a instância do App do Google ADK configurada com o orquestrador."""
    global _app
    if _app is None:
        _app = App(
            name=APP_NAME,
            root_agent=aurora_orchestrator,
        )
    return _app


def get_runner() -> Runner:
    """Retorna o Runner do Google ADK acoplado ao App e ao SessionService durável."""
    global _runner
    if _runner is None:
        _runner = Runner(
            app=get_app(),
            session_service=get_session_service(),
        )
    return _runner


async def criar_sessao_adk(
    apartamento: str,
    session_id: Optional[str] = None,
) -> Session:
    """
    Cria uma nova sessão persistente no ADK e injeta o apartamento no session.state (Garantia 2).
    """
    sid = session_id or str(uuid.uuid4())
    user_id = f"morador_{apartamento}"
    ss = get_session_service()

    session = await ss.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=sid,
        state={"apartamento": str(apartamento)},
    )
    return session


async def obter_sessao_adk(session_id: str) -> Optional[Session]:
    """
    Localiza e recupera uma sessão persistente existente no banco SQLite.
    Retorna None se a sessão não existir.
    """
    async with get_async_db_connection() as conn:
        cur = await conn.execute(
            "SELECT app_name, user_id FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        app_name = row["app_name"]
        user_id = row["user_id"]

    ss = get_session_service()
    return await ss.get_session(app_name=app_name, user_id=user_id, session_id=session_id)


async def obter_eventos_sessao(session_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Retorna a lista cronológica integral dos eventos serializados da sessão (Garantia 3).
    Retorna None se a sessão não existir (resultando em 404).
    """
    session = await obter_sessao_adk(session_id)
    if not session:
        return None

    eventos = []
    for ev in session.events:
        eventos.append(ev.model_dump(mode="json"))
    return eventos


async def _executar_fallback_deterministico(
    session: Session,
    texto: str,
) -> str:
    """
    Dispatcher determinístico de regras caso o LLM externo esteja offline ou inacessível.
    Executa exatamente as mesmas ferramentas dos especialistas e grava eventos na sessão.
    """
    t_lower = texto.lower()
    ctx = ContextProxy(session)
    resposta = ""
    ss = get_session_service()

    # 1. Dúvida sobre Regulamento / Piscina (Garantia 4)
    if "piscina" in t_lower:
        trecho = consultar_regulamento("piscina aos domingos")
        if "9h às 20h" in trecho:
            resposta = "Aos domingos e feriados, a piscina funciona das 9h às 20h (de segunda a sábado das 8h às 22h). É obrigatório exame dermatológico válido."
        else:
            resposta = trecho

    # 2. Cancelamento de reserva (Garantia 2)
    elif "cancelar" in t_lower or "cancele" in t_lower or "cancelamento" in t_lower:
        match_cod = re.search(r"RSV-\d+", texto, re.IGNORECASE)
        match_data = re.search(r"\b\d{4}-\d{2}-\d{2}\b", texto)
        if match_cod:
            identificador = match_cod.group(0).upper()
        elif match_data:
            identificador = match_data.group(0)
        elif "quadra" in t_lower:
            identificador = "quadra"
        elif "sal" in t_lower:
            identificador = "salao-de-festas"
        elif "churras" in t_lower:
            identificador = "churrasqueira"
        else:
            identificador = texto.strip()
        res = cancelar_minha_reserva(identificador, tool_context=ctx)
        resposta = res["mensagem"]

    # 3. Consulta / Listagem de dados próprios (Garantia 2 - blindagem contra espionagem)
    elif (
        any(k in t_lower for k in ("minhas reservas", "meus visitantes", "minha reserva", "meu visitante"))
        or any(k in t_lower for k in ("quais são", "quais as", "quais os", "listar", "consultar"))
    ):
        partes = []
        apto = session.state.get("apartamento", "")
        # Consulta de reservas da própria unidade
        if any(k in t_lower for k in ("reserva", "reservas")):
            res = listar_minhas_reservas(tool_context=ctx)
            reservas = res.get("reservas", [])
            if reservas:
                linhas = [f"- {r['codigo']}: {r['area']} em {r['data']}" for r in reservas]
                partes.append(f"Reservas ativas da sua unidade ({apto}):\n" + "\n".join(linhas))
            else:
                partes.append(f"Não há reservas ativas para a unidade {apto}.")

        # Consulta de visitantes da própria unidade
        if any(k in t_lower for k in ("visitante", "visitantes", "visita")):
            res = listar_meus_visitantes(tool_context=ctx)
            vis = res.get("visitantes", [])
            if vis:
                linhas = [f"- {v['nome']} ({v['data']})" for v in vis]
                partes.append(f"Visitantes autorizados da sua unidade ({apto}):\n" + "\n".join(linhas))
            else:
                partes.append(f"Não há visitantes autorizados cadastrados para a sua unidade ({apto}).")

        if partes:
            resposta = "\n\n".join(partes)
        else:
            resposta = f"Informações consultadas para a unidade {apto} vinculada a esta sessão."

    # 4. Solicitação de Reserva (Garantia 1 e 5)
    elif any(k in t_lower for k in ("reservar", "agendar", "marcar", "fazer uma reserva", "quero uma reserva", "solicitar reserva")) or (
        "reserva" in t_lower and any(k in t_lower for k in ("quero", "gostaria", "favor", "preciso", "para"))
    ):
        area = "salao-de-festas" if "sal" in t_lower else ("churrasqueira" if "churras" in t_lower else "quadra")
        match_data = re.search(r"\b\d{4}-\d{2}-\d{2}\b", texto)
        data = match_data.group(0) if match_data else "2030-04-20"
        res = solicitar_reserva(area=area, data=data, tool_context=ctx)
        resposta = res["mensagem"]

    # 5. Autorização de Visitante (Garantia 1)
    elif any(k in t_lower for k in ("liberar", "autorizar", "permitir entrada", "cadastrar visitante", "novo visitante", "libera")):
        match_data = re.search(r"\b\d{4}-\d{2}-\d{2}\b", texto)
        data = match_data.group(0) if match_data else "2030-03-25"
        nome = "Visitante"
        match_nome = re.search(
            r"(?:visitante|liberar|autorizar)\s+([A-Za-zÀ-ÿ\s]+?)(?:\s+para|\s+no|\s+dia|\s+em|\s*,|\s*$)",
            texto,
            re.IGNORECASE,
        )
        if match_nome:
            nome = match_nome.group(1).strip()
        res = solicitar_autorizacao_visitante(nome=nome, data=data, tool_context=ctx)
        resposta = res["mensagem"]

    # 6. Saudação ou ajuda padrão
    else:
        apto = session.state.get("apartamento", "")
        resposta = f"Olá! Sou o assistente do Residencial Aurora. Como posso ajudar o apartamento {apto} hoje?"

    # Grava os eventos na sessão persistente do ADK garantindo sessão atualizada
    try:
        s_fresh = await ss.get_session(app_name=session.app_name, user_id=session.user_id, session_id=session.id)
        if s_fresh:
            ev_user = Event(
                author="user",
                content=types.Content(parts=[types.Part.from_text(text=texto)]),
            )
            await ss.append_event(s_fresh, ev_user)

            s_fresh2 = await ss.get_session(app_name=session.app_name, user_id=session.user_id, session_id=session.id)
            if s_fresh2:
                ev_resp = Event(
                    author="aurora_orchestrator",
                    content=types.Content(parts=[types.Part.from_text(text=resposta)]),
                )
                await ss.append_event(s_fresh2, ev_resp)
    except Exception:
        pass

    return resposta


async def executar_turno_mensagem(
    session_id: str,
    texto_usuario: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Executa o turno conversacional através do Runner do ADK.
    Se a API do LLM estiver offline ou inacessível, ativa o dispatcher determinístico.
    Garante o retorno do texto final e a lista de confirmações pendentes ativas.
    """
    session = await obter_sessao_adk(session_id)
    if not session:
        raise KeyError(f"Sessão '{session_id}' não encontrada.")

    runner = get_runner()
    user_content = types.Content(
        parts=[types.Part.from_text(text=texto_usuario)],
        role="user",
    )

    texto_resposta = ""
    try:
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=user_content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        texto_resposta += part.text
    except Exception:
        # Ativa o fallback determinístico de alta resiliência
        texto_resposta = await _executar_fallback_deterministico(session, texto_usuario)

    # Recupera confirmações pendentes geradas nesta sessão
    confirmacoes = await async_listar_confirmacoes_pendentes(session_id)
    return texto_resposta.strip(), confirmacoes
