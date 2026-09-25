"""
Testes unitários e de integração para a arquitetura multi-agente Google ADK.
Valida as Garantias 2 e 4:
- Injeção de identidade a partir de context.state (sem parâmetro de apartamento para o LLM);
- Isolamento do regulamento (não carregado no orquestrador e busca pontual sem vazamento de outros capítulos);
- Persistência de sessões no SqliteSessionService.
"""

import pytest
from google.adk.tools import FunctionTool

from app.agents.orchestrator import aurora_orchestrator
from app.agents.runtime import criar_sessao_adk, obter_eventos_sessao, obter_sessao_adk
from app.agents.specialists.regulamento import regulamento_specialist
from app.agents.specialists.reservas import reservas_specialist
from app.agents.specialists.visitantes import visitantes_specialist
from app.agents.tools.regulamento_tools import consultar_regulamento
from app.agents.tools.reservas_tools import solicitar_reserva
from app.agents.tools.visitantes_tools import solicitar_autorizacao_visitante


def test_garantia_4_orquestrador_sem_regulamento():
    """Garantia 4: As instruções do orquestrador NÃO contêm o regulamento interno."""
    prompt = aurora_orchestrator.instruction
    assert "Capítulo" not in prompt
    assert "Art." not in prompt
    assert len(prompt) < 1500, "O prompt do orquestrador não pode ser volumoso."


def test_orquestrador_subagentes():
    """O orquestrador deve possuir os 3 especialistas configurados."""
    sub_names = {sub.name for sub in aurora_orchestrator.sub_agents}
    assert "reservas_specialist" in sub_names
    assert "visitantes_specialist" in sub_names
    assert "regulamento_specialist" in sub_names


def test_garantia_2_tools_omitem_parametro_apartamento_para_llm():
    """
    Garantia 2: Ferramentas sensíveis extraem o apartamento de tool_context.state,
    não permitindo que o LLM forneça ou adultere o apartamento.
    """
    ft_reserva = FunctionTool(func=solicitar_reserva)
    decl_reserva = ft_reserva._get_declaration()
    schema_reserva = decl_reserva.parameters_json_schema or {}
    params_reserva = list(schema_reserva.get("properties", {}).keys())
    assert "apartamento" not in params_reserva
    assert "area" in params_reserva
    assert "data" in params_reserva

    ft_visitante = FunctionTool(func=solicitar_autorizacao_visitante)
    decl_visitante = ft_visitante._get_declaration()
    schema_visitante = decl_visitante.parameters_json_schema or {}
    params_visitante = list(schema_visitante.get("properties", {}).keys())
    assert "apartamento" not in params_visitante
    assert "nome" in params_visitante
    assert "data" in params_visitante


def test_garantia_4_consulta_pontual_regulamento():
    """
    Garantia 4: A busca sobre piscina aos domingos deve retornar o horário correto (9h às 20h)
    sem carregar capítulos desconexos (como Silêncio, Mudanças, Garagem).
    """
    resultado = consultar_regulamento("horário da piscina aos domingos")
    assert "Piscina" in resultado
    assert "9h às 20h" in resultado
    # Verifica ausência de outros capítulos
    assert "Capítulo I:" not in resultado
    assert "Capítulo III:" not in resultado
    assert "Capítulo IX:" not in resultado
    assert "Capítulo XI:" not in resultado


@pytest.mark.asyncio
async def test_garantia_3_sessao_adk_sqlite_duravel():
    """Garantia 3: Criação de sessão e persistência de estado no SQLite."""
    sess = await criar_sessao_adk(apartamento="202")
    assert sess.state.get("apartamento") == "202"

    recup = await obter_sessao_adk(sess.id)
    assert recup is not None
    assert recup.id == sess.id
    assert recup.state.get("apartamento") == "202"

    eventos = await obter_eventos_sessao(sess.id)
    assert isinstance(eventos, list)
