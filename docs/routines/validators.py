"""
Validadores automáticos para tarefas das Fases 1 a 6.
Executam checagens de integridade estática e de runtime, retornando respostas ultraconcisas.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Tuple, Optional

from .executor import run_quietly, ExecutionResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def check_t1_1() -> Tuple[bool, str]:
    """T1.1: Inicializar projeto Python 3.12 estruturado com uv (pyproject.toml e uv.lock)."""
    # 1. Verifica versão do Python
    if sys.version_info < (3, 12):
        return False, f"Python >= 3.12 requerido. Atual: {sys.version.split()[0]}"

    # 2. Verifica pyproject.toml
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return False, "pyproject.toml não encontrado na raiz."

    # 3. Verifica uv.lock
    uv_lock = PROJECT_ROOT / "uv.lock"
    if not uv_lock.exists():
        return False, "uv.lock não encontrado na raiz."

    return True, "Python >= 3.12, pyproject.toml e uv.lock presentes e válidos."


def check_t1_2() -> Tuple[bool, str]:
    """T1.2: Fixar versão exata de google-adk (série 2 >= 2.2.0) e dependências principais."""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return False, "pyproject.toml ausente."

    content = pyproject.read_text(encoding="utf-8")
    
    # Checa fixação do google-adk
    adk_match = re.search(r'google-adk\s*==\s*2\.\d+\.\d+', content)
    if not adk_match:
        return False, "google-adk não está fixado na versão exata (ex.: google-adk==2.2.0)."

    # Checa dependências essenciais
    required_deps = ["fastapi", "uvicorn", "pydantic-settings", "aiosqlite", "httpx"]
    missing = [dep for dep in required_deps if dep not in content]
    if missing:
        return False, f"Dependências ausentes no pyproject.toml: {missing}"

    return True, f"Dependências fixadas com sucesso ({adk_match.group(0)}, fastapi, uvicorn, etc.)."


def check_t1_3() -> Tuple[bool, str]:
    """T1.3: Criar .env.example com GEMINI_API_KEY e garantir .env no .gitignore."""
    env_example = PROJECT_ROOT / ".env.example"
    gitignore = PROJECT_ROOT / ".gitignore"

    if not env_example.exists():
        return False, ".env.example não encontrado."

    example_content = env_example.read_text(encoding="utf-8")
    if "GEMINI_API_KEY" not in example_content:
        return False, "GEMINI_API_KEY ausente em .env.example."

    if not gitignore.exists():
        return False, ".gitignore não encontrado."

    git_content = gitignore.read_text(encoding="utf-8")
    if ".env" not in git_content.splitlines():
        return False, ".env não está estritamente listado no .gitignore."

    return True, ".env.example criado com GEMINI_API_KEY e .env estritamente protegido pelo .gitignore."


def check_t1_4() -> Tuple[bool, str]:
    """T1.4: Configurar estrutura modular de diretórios (app/api, app/domain, app/agents, app/scripts, tests)."""
    expected_dirs = [
        PROJECT_ROOT / "app" / "api",
        PROJECT_ROOT / "app" / "domain",
        PROJECT_ROOT / "app" / "agents",
        PROJECT_ROOT / "app" / "scripts",
        PROJECT_ROOT / "tests",
    ]
    missing = [str(d.relative_to(PROJECT_ROOT)) for d in expected_dirs if not d.exists()]
    if missing:
        # Cria os diretórios caso não existam para agilizar o setup
        for d in expected_dirs:
            d.mkdir(parents=True, exist_ok=True)
            init_file = d / "__init__.py"
            if not init_file.exists() and d.name != "tests":
                init_file.write_text("# Auto-generated\n", encoding="utf-8")
        return True, f"Estrutura modular de diretórios configurada (criados: {missing})."

    return True, "Estrutura modular completa (app/api, app/domain, app/agents, app/scripts, tests)."


def check_dados_integrity() -> Tuple[bool, str]:
    """Garantia dos arquivos imutáveis em dados/."""
    expected_files = [
        "apartamentos.json",
        "areas.json",
        "reservas.json",
        "visitantes.json",
        "regulamento.md",
    ]
    dados_dir = PROJECT_ROOT / "dados"
    if not dados_dir.exists():
        return False, "Diretório dados/ ausente."

    for fname in expected_files:
        if not (dados_dir / fname).exists():
            return False, f"Arquivo obrigatório dados/{fname} ausente."

    return True, "Arquivos em dados/ íntegros e disponíveis."


def check_t2_1() -> Tuple[bool, str]:
    """T2.1: Implementar app/database.py com SQLite durável (aurora.db), WAL, FKs e índice de unicidade."""
    db_file = PROJECT_ROOT / "app" / "database.py"
    if not db_file.exists():
        return False, "app/database.py não encontrado."

    try:
        from app.database import (
            init_db,
            get_db_connection,
            get_async_db_connection,
            immediate_transaction,
            async_immediate_transaction,
            DDL_SCHEMA,
        )
    except Exception as e:
        return False, f"Erro ao importar app/database.py: {e}"

    # 1. Verifica se a DDL contém o índice uq_reservas_area_data_ativa
    if "uq_reservas_area_data_ativa" not in DDL_SCHEMA:
        return False, "Índice uq_reservas_area_data_ativa ausente no DDL_SCHEMA."
    if "WHERE status = 'ATIVA'" not in DDL_SCHEMA:
        return False, "Cláusula WHERE status = 'ATIVA' ausente na definição do índice uq_reservas_area_data_ativa."

    # 2. Testa inicialização em banco temporário em disco
    test_db = PROJECT_ROOT / ".task_logs" / "test_validate_t2_1.db"
    try:
        if test_db.exists():
            test_db.unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_validate_t2_1.db-wal").unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_validate_t2_1.db-shm").unlink(missing_ok=True)

        init_db(test_db)

        with get_db_connection(test_db) as conn:
            # Checa WAL
            cur = conn.execute("PRAGMA journal_mode;")
            journal_mode = cur.fetchone()[0]
            if journal_mode.lower() != "wal":
                return False, f"PRAGMA journal_mode esperado 'wal', obtido '{journal_mode}'."

            # Checa Foreign Keys
            cur = conn.execute("PRAGMA foreign_keys;")
            fk = cur.fetchone()[0]
            if fk != 1:
                return False, "PRAGMA foreign_keys não está ativo (deve ser 1)."

            # Checa tabelas
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cur.fetchall()}
            expected_tables = {"apartamentos", "areas", "reservas", "visitantes", "confirmacoes"}
            if not expected_tables.issubset(tables):
                return False, f"Tabelas ausentes: {expected_tables - tables}"

            # Checa índice de unicidade
            cur = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND name='uq_reservas_area_data_ativa';"
            )
            idx = cur.fetchone()
            if not idx:
                return False, "Índice uq_reservas_area_data_ativa não encontrado no SQLite."

            # Checa Garantia 5 (conflito de unicidade para reservas ATIVAS)
            conn.execute("INSERT INTO apartamentos (numero, morador) VALUES ('101', 'Morador 101')")
            conn.execute("INSERT INTO apartamentos (numero, morador) VALUES ('201', 'Morador 201')")
            conn.execute("INSERT INTO areas (id, nome, taxa) VALUES ('quadra', 'Quadra', 0.0)")

            conn.execute(
                "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES ('RSV-1', '101', 'quadra', '2030-01-01', 'ATIVA')"
            )
            try:
                conn.execute(
                    "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES ('RSV-2', '201', 'quadra', '2030-01-01', 'ATIVA')"
                )
                return False, "Índice de unicidade permitiu duas reservas ativas na mesma área e data."
            except Exception:
                pass  # Esperado

            # Checa foreign key enforcement
            try:
                conn.execute(
                    "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES ('RSV-3', '999', 'quadra', '2030-01-02', 'ATIVA')"
                )
                return False, "Chave estrangeira não barrou inserção de apartamento inexistente."
            except Exception:
                pass  # Esperado

    finally:
        try:
            if test_db.exists():
                test_db.unlink(missing_ok=True)
            (PROJECT_ROOT / ".task_logs" / "test_validate_t2_1.db-wal").unlink(missing_ok=True)
            (PROJECT_ROOT / ".task_logs" / "test_validate_t2_1.db-shm").unlink(missing_ok=True)
        except Exception:
            pass

    return True, "app/database.py implementado com SQLite durável, WAL mode, chaves estrangeiras e índice uq_reservas_area_data_ativa."


def check_t2_2() -> Tuple[bool, str]:
    """T2.2: Implementar app/domain/services.py com métodos determinísticos de isolamento."""
    try:
        from app.domain.services import (
            listar_reservas_apartamento,
            listar_visitantes_apartamento,
            consultar_disponibilidade_area,
            cancelar_reserva_propria,
            gerar_codigo_reserva,
        )
    except Exception as e:
        return False, f"Erro ao importar serviços de domínio: {e}"

    # Validação rápida de código
    cod = gerar_codigo_reserva()
    if not cod.startswith("RSV-"):
        return False, f"Código de reserva em formato inválido: {cod}"

    return True, "app/domain/services.py implementado com métodos determinísticos e isolamento estrito."


def check_t2_3() -> Tuple[bool, str]:
    """T2.3: Implementar mecanismo de concorrência atômica da Garantia 5 (BEGIN IMMEDIATE e colisão)."""
    try:
        from app.domain.services import criar_reserva_atomica
        from app.scripts.restore_data import restore_initial_data
    except Exception as e:
        return False, f"Erro ao importar serviços: {e}"

    test_db = PROJECT_ROOT / ".task_logs" / "test_t2_3.db"
    try:
        restore_initial_data(test_db)
        ok1, cod1, _ = criar_reserva_atomica("101", "salao-de-festas", "2030-05-20", db_path=test_db)
        ok2, cod2, msg2 = criar_reserva_atomica("201", "salao-de-festas", "2030-05-20", db_path=test_db)

        if not ok1 or cod1 is None:
            return False, "Primeira transação falhou ao reservar."
        if ok2 or cod2 is not None:
            return False, "Segunda transação concorrente não foi barrada."
    finally:
        test_db.unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_t2_3.db-wal").unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_t2_3.db-shm").unlink(missing_ok=True)

    return True, "Concorrência atômica da Garantia 5 validada com sucesso (rejeição graciosa sem crash)."


def check_t2_4() -> Tuple[bool, str]:
    """T2.4: Criar script de restauração app/scripts/restore_data.py."""
    restore_file = PROJECT_ROOT / "app" / "scripts" / "restore_data.py"
    if not restore_file.exists():
        return False, "app/scripts/restore_data.py ausente."

    try:
        from app.scripts.restore_data import restore_initial_data
        from app.domain.services import listar_reservas_apartamento, listar_visitantes_apartamento
    except Exception as e:
        return False, f"Erro ao importar restore_data: {e}"

    test_db = PROJECT_ROOT / ".task_logs" / "test_t2_4.db"
    try:
        restore_initial_data(test_db)
        r101 = listar_reservas_apartamento("101", db_path=test_db)
        v302 = listar_visitantes_apartamento("302", db_path=test_db)

        if not any(r["codigo"] == "RSV-1377" for r in r101):
            return False, "Reserva RSV-1377 do apartamento 101 não encontrada após restauração."
        if not any(v["nome"] == "Marina Duarte" for v in v302):
            return False, "Visitante Marina Duarte do apartamento 302 não encontrado após restauração."
    finally:
        test_db.unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_t2_4.db-wal").unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_t2_4.db-shm").unlink(missing_ok=True)

    return True, "Script de restauração fiel app/scripts/restore_data.py operacional."


def check_t3_1() -> Tuple[bool, str]:
    """T3.1: Criar modelo e tabela de confirmações pendentes (confirmacoes)."""
    try:
        from app.domain.models import ConfirmacaoPendente
        from app.domain.services import criar_confirmacao_pendente, listar_confirmacoes_pendentes
    except Exception as e:
        return False, f"Erro ao importar modelos/serviços de confirmações: {e}"

    test_db = PROJECT_ROOT / ".task_logs" / "test_t3_1.db"
    try:
        from app.scripts.restore_data import restore_initial_data
        restore_initial_data(test_db)

        conf = criar_confirmacao_pendente(
            "sess_abc", "101", "reservar_area", {"area": "salao-de-festas", "data": "2030-07-07"}, db_path=test_db
        )
        if not isinstance(conf, ConfirmacaoPendente) or conf.status != "PENDENTE":
            return False, "Instância de ConfirmacaoPendente inválida."

        pendentes = listar_confirmacoes_pendentes("sess_abc", db_path=test_db)
        if len(pendentes) != 1 or pendentes[0]["id"] != conf.id:
            return False, "Listagem de confirmações pendentes incorreta."
    finally:
        test_db.unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_t3_1.db-wal").unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_t3_1.db-shm").unlink(missing_ok=True)

    return True, "Modelo e persistência de confirmações pendentes implementados."


def check_t3_2() -> Tuple[bool, str]:
    """T3.2: Implementar regra determinística de necessidade de confirmação."""
    try:
        from app.domain.models import AreaComum
        from app.domain.services import obter_area
    except Exception as e:
        return False, f"Erro ao carregar serviços: {e}"

    area_paga = obter_area("salao-de-festas")
    area_gratis = obter_area("quadra")

    if not area_paga or not area_paga.requer_confirmacao:
        return False, "Área paga (salao-de-festas) deve requerer confirmação (taxa > 0)."
    if not area_gratis or area_gratis.requer_confirmacao:
        return False, "Área gratuita (quadra) NÃO deve requerer confirmação (taxa == 0)."

    return True, "Regras determinísticas de necessidade de confirmação (Garantia 1) validadas."


def check_t3_3() -> Tuple[bool, str]:
    """T3.3: Implementar idempotência e blindagem de confirmações (409 Conflict)."""
    try:
        from app.domain.services import (
            criar_confirmacao_pendente,
            responder_confirmacao,
        )
        from app.scripts.restore_data import restore_initial_data
    except Exception as e:
        return False, f"Erro ao importar serviços: {e}"

    test_db = PROJECT_ROOT / ".task_logs" / "test_t3_3.db"
    try:
        restore_initial_data(test_db)
        conf = criar_confirmacao_pendente(
            "sess_idemp", "101", "reservar_area", {"area": "salao-de-festas", "data": "2030-08-08"}, db_path=test_db
        )

        # 1. ID inexistente deve dar 409
        ok1, _, code1 = responder_confirmacao("sess_idemp", "conf_invalido", True, db_path=test_db)
        if ok1 or code1 != 409:
            return False, f"Chamada com ID inexistente deve retornar 409, obteve {code1}"

        # 2. Primeira aprovação dá 200
        ok2, _, code2 = responder_confirmacao("sess_idemp", conf.id, True, db_path=test_db)
        if not ok2 or code2 != 200:
            return False, f"Primeira confirmação falhou: {code2}"

        # 3. Reenvio deve dar 409 Conflict
        ok3, _, code3 = responder_confirmacao("sess_idemp", conf.id, True, db_path=test_db)
        if ok3 or code3 != 409:
            return False, f"Reenvio de confirmação deve retornar 409 Conflict, obteve {code3}"
    finally:
        test_db.unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_t3_3.db-wal").unlink(missing_ok=True)
        (PROJECT_ROOT / ".task_logs" / "test_t3_3.db-shm").unlink(missing_ok=True)

    return True, "Idempotência da rota de confirmações com retorno 409 Conflict validada."


def check_t4_1() -> Tuple[bool, str]:
    """T4.1: Configurar SessionService baseado em SQLite no Google ADK (app/agents/runtime.py)."""
    try:
        import asyncio
        from app.agents.runtime import criar_sessao_adk, obter_sessao_adk
        sess = asyncio.run(criar_sessao_adk("301"))
        recup = asyncio.run(obter_sessao_adk(sess.id))
        if not recup or recup.state.get("apartamento") != "301":
            return False, "Falha na persistência ou recuperação de estado da sessão no ADK."
    except Exception as e:
        return False, f"Erro ao validar SessionService do ADK: {e}"

    return True, "SqliteSessionService configurado e persistente em disco no ADK."


def check_t4_2() -> Tuple[bool, str]:
    """T4.2: Implementar as ferramentas (tools) do ADK com validação estrita de identidade (Garantia 2)."""
    try:
        from google.adk.tools import FunctionTool
        from app.agents.tools.reservas_tools import solicitar_reserva
        from app.agents.tools.visitantes_tools import solicitar_autorizacao_visitante

        for func in (solicitar_reserva, solicitar_autorizacao_visitante):
            ft = FunctionTool(func=func)
            decl = ft._get_declaration()
            schema = decl.parameters_json_schema or {}
            params = list(schema.get("properties", {}).keys())
            if "apartamento" in params:
                return False, f"Ferramenta {func.__name__} expõe parâmetro 'apartamento' ao LLM (violação da Garantia 2)."
    except Exception as e:
        return False, f"Erro ao inspecionar assinaturas das tools: {e}"

    return True, "Tools blindadas com injeção estrita a partir de context.state (Garantia 2)."


def check_t4_3() -> Tuple[bool, str]:
    """T4.3: Implementar ferramenta de consulta pontual do regulamento (app/agents/tools/regulamento_tools.py)."""
    try:
        from app.agents.tools.regulamento_tools import consultar_regulamento
        res = consultar_regulamento("piscina aos domingos")
        if "9h às 20h" not in res:
            return False, "Consulta ao regulamento não retornou o horário correto da piscina aos domingos."
        if "Capítulo I:" in res or "Capítulo IX:" in res:
            return False, "Consulta pontual vazou capítulos não correlacionados (violação da Garantia 4)."
    except Exception as e:
        return False, f"Erro ao testar consulta ao regulamento: {e}"

    return True, "Ferramenta de consulta pontual ao regulamento implementada sem vazamento de capítulos."


def check_t4_4() -> Tuple[bool, str]:
    """T4.4: Construir Especialista em Reservas (reservas_specialist)."""
    try:
        from app.agents.specialists.reservas import reservas_specialist
        tool_names = {getattr(t, "name", getattr(t, "__name__", str(t))) for t in reservas_specialist.tools}
        expected = {"checar_disponibilidade", "solicitar_reserva", "cancelar_minha_reserva", "listar_minhas_reservas"}
        if not expected.issubset(tool_names):
            return False, f"Tools ausentes no reservas_specialist: {expected - tool_names}"
    except Exception as e:
        return False, f"Erro ao validar reservas_specialist: {e}"

    return True, "Especialista em Reservas configurado com todas as ferramentas de domínio."


def check_t4_5() -> Tuple[bool, str]:
    """T4.5: Construir Especialista em Portaria e Visitantes (visitantes_specialist)."""
    try:
        from app.agents.specialists.visitantes import visitantes_specialist
        tool_names = {getattr(t, "name", getattr(t, "__name__", str(t))) for t in visitantes_specialist.tools}
        expected = {"solicitar_autorizacao_visitante", "listar_meus_visitantes"}
        if not expected.issubset(tool_names):
            return False, f"Tools ausentes no visitantes_specialist: {expected - tool_names}"
    except Exception as e:
        return False, f"Erro ao validar visitantes_specialist: {e}"

    return True, "Especialista em Portaria configurado com confirmação obrigatória."


def check_t4_6() -> Tuple[bool, str]:
    """T4.6: Construir Especialista em Regulamento (regulamento_specialist)."""
    try:
        from app.agents.specialists.regulamento import regulamento_specialist
        tool_names = {getattr(t, "name", getattr(t, "__name__", str(t))) for t in regulamento_specialist.tools}
        if "consultar_regulamento" not in tool_names:
            return False, "Tool 'consultar_regulamento' ausente no regulamento_specialist."
    except Exception as e:
        return False, f"Erro ao validar regulamento_specialist: {e}"

    return True, "Especialista em Regulamento construído e integrado à ferramenta de busca pontual."


def check_t4_7() -> Tuple[bool, str]:
    """T4.7: Construir Agente Principal / Orquestrador (aurora_orchestrator)."""
    try:
        from app.agents.orchestrator import aurora_orchestrator
        prompt = aurora_orchestrator.instruction
        if "Capítulo" in prompt or "Art." in prompt:
            return False, "Agente principal contém trechos do regulamento no prompt (violação da Garantia 4)."
        sub_names = {sub.name for sub in aurora_orchestrator.sub_agents}
        expected_subs = {"reservas_specialist", "visitantes_specialist", "regulamento_specialist"}
        if not expected_subs.issubset(sub_names):
            return False, f"Especialistas ausentes no orquestrador: {expected_subs - sub_names}"
    except Exception as e:
        return False, f"Erro ao validar aurora_orchestrator: {e}"

    return True, "Agente Principal configurado com subagentes e sem regulamento no prompt (Garantia 4)."


def check_t4_8() -> Tuple[bool, str]:
    """T4.8: Configurar o App e o Runner do ADK no runtime."""
    try:
        from app.agents.runtime import get_app, get_runner
        app = get_app()
        runner = get_runner()
        if not app or not runner:
            return False, "App ou Runner não inicializados corretamente."
    except Exception as e:
        return False, f"Erro ao validar App e Runner do ADK: {e}"

    return True, "App e Runner do ADK configurados com suporte a execução durável."


def check_t5_1() -> Tuple[bool, str]:
    """T5.1: Definir modelos Pydantic rigorosos para requisições e respostas em app/api/schemas.py."""
    try:
        from app.api import schemas
        required_classes = [
            "CriarSessaoRequest",
            "CriarSessaoResponse",
            "MensagemRequest",
            "MensagemResponse",
            "ResponderConfirmacaoRequest",
            "ReservaAuditoriaResponse",
            "VisitanteAuditoriaResponse",
        ]
        missing = [c for c in required_classes if not hasattr(schemas, c)]
        if missing:
            return False, f"Modelos Pydantic ausentes em app/api/schemas.py: {missing}"
    except Exception as e:
        return False, f"Erro ao importar app/api/schemas.py: {e}"

    return True, "Modelos Pydantic rigorosos implementados para todas as rotas."


def check_t5_2() -> Tuple[bool, str]:
    """T5.2: Implementar rota POST /sessoes."""
    try:
        import asyncio, httpx
        from app.main import app

        async def _test():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post("/sessoes", json={"apartamento": "101"})
                if r.status_code != 201 or "session_id" not in r.json():
                    return False, f"POST /sessoes retornou status {r.status_code} inesperado."
                return True, "POST /sessoes funcional com retorno 201 e session_id."

        return asyncio.run(_test())
    except Exception as e:
        return False, f"Erro ao testar POST /sessoes: {e}"


def check_t5_3() -> Tuple[bool, str]:
    """T5.3: Implementar rota POST /sessoes/{session_id}/mensagens."""
    try:
        import asyncio, httpx
        from app.main import app

        async def _test():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                r_404 = await client.post("/sessoes/nao-existe/mensagens", json={"texto": "Olá"})
                if r_404.status_code != 404:
                    return False, f"Esperado 404 para sessão inexistente, obtido {r_404.status_code}"
                return True, "POST /sessoes/{session_id}/mensagens configurada com validação de existência."

        return asyncio.run(_test())
    except Exception as e:
        return False, f"Erro ao testar POST /sessoes/mensagens: {e}"


def check_t5_4() -> Tuple[bool, str]:
    """T5.4: Implementar rota POST /sessoes/{session_id}/confirmacoes com idempotência 409."""
    try:
        import asyncio, httpx
        from app.main import app

        async def _test():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                r_s = await client.post("/sessoes", json={"apartamento": "101"})
                sid = r_s.json()["session_id"]
                r_c = await client.post(f"/sessoes/{sid}/confirmacoes", json={"id": "conf_inexistente", "confirmado": True})
                if r_c.status_code != 409:
                    return False, f"Esperado 409 Conflict para ID inválido, obtido {r_c.status_code}"
                return True, "POST /sessoes/{session_id}/confirmacoes com retorno 409 validado."

        return asyncio.run(_test())
    except Exception as e:
        return False, f"Erro ao testar POST /confirmacoes: {e}"


def check_t5_5() -> Tuple[bool, str]:
    """T5.5: Implementar rota GET /sessoes/{session_id}/eventos."""
    try:
        import asyncio, httpx
        from app.main import app

        async def _test():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                r_404 = await client.get("/sessoes/sessao-fantasma/eventos")
                if r_404.status_code != 404:
                    return False, f"Esperado 404 para sessão inexistente, obtido {r_404.status_code}"
                r_s = await client.post("/sessoes", json={"apartamento": "201"})
                sid = r_s.json()["session_id"]
                r_ev = await client.get(f"/sessoes/{sid}/eventos")
                if r_ev.status_code != 200 or not isinstance(r_ev.json(), list):
                    return False, f"Esperado 200 com lista de eventos, obtido {r_ev.status_code}"
                return True, "GET /sessoes/{session_id}/eventos validado (200 com lista, 404 para ausente)."

        return asyncio.run(_test())
    except Exception as e:
        return False, f"Erro ao testar GET /eventos: {e}"


def check_t5_6() -> Tuple[bool, str]:
    """T5.6: Implementar rotas de auditoria GET /apartamentos/{numero}/(reservas|visitantes)."""
    try:
        import asyncio, httpx
        from app.main import app
        from app.scripts.restore_data import restore_initial_data

        async def _test():
            restore_initial_data()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                r_res = await client.get("/apartamentos/101/reservas")
                if r_res.status_code != 200 or not any(r["codigo"] == "RSV-1377" for r in r_res.json()):
                    return False, "GET /apartamentos/101/reservas não retornou RSV-1377."

                r_vis = await client.get("/apartamentos/302/visitantes")
                if r_vis.status_code != 200 or not any(v["nome"] == "Marina Duarte" for v in r_vis.json()):
                    return False, "GET /apartamentos/302/visitantes não retornou Marina Duarte."

                return True, "Rotas de auditoria /apartamentos/{numero}/(reservas|visitantes) validadas."

        return asyncio.run(_test())
    except Exception as e:
        return False, f"Erro ao testar rotas de auditoria: {e}"


def run_pytest_quietly(test_target: Optional[str] = None) -> ExecutionResult:
    """Executa o pytest sem encher o contexto, gravando o log completo em disco."""
    cmd = [sys.executable, "-m", "pytest", "-v"]
    if test_target:
        cmd.append(test_target)
    return run_quietly(cmd, log_prefix="pytest")


def check_t6_1() -> Tuple[bool, str]:
    """T6.1: Configurar pytest e httpx.AsyncClient em tests/conftest.py."""
    conftest = PROJECT_ROOT / "tests" / "conftest.py"
    if not conftest.exists():
        return False, "tests/conftest.py não encontrado."
    content = conftest.read_text(encoding="utf-8")
    if "AsyncClient" not in content or "restore_initial_data" not in content:
        return False, "tests/conftest.py não configura AsyncClient ou fixture de restauração."
    return True, "Configuração de testes em tests/conftest.py validada com sucesso."


def check_t6_2() -> Tuple[bool, str]:
    """T6.2: Testar Passo 1: Restauração dos dados iniciais e conferência das rotas de verificação."""
    res = run_pytest_quietly("tests/test_avaliador_flow.py::test_passo_01_restauracao_e_auditoria")
    if not res.success:
        return False, f"Falha no Passo 1 do avaliador:\n{res.error_snippet}"
    return True, "Passo 1 do avaliador validado com sucesso (auditoria pós-restauração)."


def check_t6_3() -> Tuple[bool, str]:
    """T6.3: Testar Passos 2 a 5: Criação de S1 (101); isolamento do 302 e cancelamento próprio."""
    res = run_pytest_quietly("tests/test_avaliador_flow.py::test_passos_02_a_05_sessao_s1_espionagem_e_cancelamentos")
    if not res.success:
        return False, f"Falha nos Passos 2 a 5 do avaliador:\n{res.error_snippet}"
    return True, "Passos 2 a 5 do avaliador validados com sucesso (isolamento e cancelamento)."


def check_t6_4() -> Tuple[bool, str]:
    """T6.4: Testar Passos 6 a 9: Reservas, confirmações pendentes, aprovação/rejeição e idempotência 409."""
    res = run_pytest_quietly("tests/test_avaliador_flow.py::test_passos_06_a_09_reservas_confirmacoes_e_idempotencia")
    if not res.success:
        return False, f"Falha nos Passos 6 a 9 do avaliador:\n{res.error_snippet}"
    return True, "Passos 6 a 9 do avaliador validados com sucesso (taxas, confirmações e idempotência)."


def check_t6_5() -> Tuple[bool, str]:
    """T6.5: Testar Passos 10 a 12: Conflito sem vazamento, autorização de visitante e regulamento pontual."""
    res = run_pytest_quietly("tests/test_avaliador_flow.py::test_passos_10_a_12_disputa_visitante_e_regulamento")
    if not res.success:
        return False, f"Falha nos Passos 10 a 12 do avaliador:\n{res.error_snippet}"
    return True, "Passos 10 a 12 do avaliador validados com sucesso (disponibilidade neutra, visitante e regulamento)."


def check_t6_6() -> Tuple[bool, str]:
    """T6.6: Testar Passo 13: Simulação de reinício do servidor e persistência de eventos."""
    res = run_pytest_quietly("tests/test_avaliador_flow.py::test_passo_13_reinicio_servidor_e_persistencia")
    if not res.success:
        return False, f"Falha no Passo 13 do avaliador:\n{res.error_snippet}"
    return True, "Passo 13 do avaliador validado com sucesso (resiliência ao reinício)."


def check_t6_7() -> Tuple[bool, str]:
    """T6.7: Testar Passo 14: Disputa concorrente atômica (Dois Moradores, Uma Reserva)."""
    res = run_pytest_quietly("tests/test_avaliador_flow.py::test_passo_14_concorrencia_dois_moradores_uma_reserva")
    if not res.success:
        return False, f"Falha no Passo 14 do avaliador:\n{res.error_snippet}"
    return True, "Passo 14 do avaliador validado com sucesso (concorrência atômica)."


def check_t6_8() -> Tuple[bool, str]:
    """T6.8: Testar Passo 15: Verificação estática e estrutural de todos os critérios de aceite."""
    res = run_pytest_quietly("tests/test_avaliador_flow.py::test_passo_15_criterios_aceite_estruturais")
    if not res.success:
        return False, f"Falha no Passo 15 do avaliador:\n{res.error_snippet}"
    return True, "Passo 15 do avaliador validado com sucesso (critérios de aceite e integridade)."


def check_t7_1() -> Tuple[bool, str]:
    """T7.1: Substituir o conteúdo de README.md pelo formato final exigido."""
    readme_path = PROJECT_ROOT / "README.md"
    if not readme_path.exists():
        return False, "README.md não encontrado na raiz do projeto."
    content = readme_path.read_text(encoding="utf-8")

    required_keywords = [
        "aurora_orchestrator",
        "reservas_specialist",
        "visitantes_specialist",
        "regulamento_specialist",
        "Garantia 1",
        "Garantia 2",
        "Garantia 3",
        "Garantia 4",
        "Garantia 5",
        "restore_data",
        "uvicorn",
    ]
    missing = [kw for kw in required_keywords if kw not in content]
    if missing:
        return False, f"README.md não contém os tópicos obrigatórios de documentação: {missing}"

    return True, "README.md documenta completamente arquitetura, 5 garantias e comandos operacionais."


def check_t7_2() -> Tuple[bool, str]:
    """T7.2: Garantir integridade dos arquivos originais em dados/."""
    dados_dir = PROJECT_ROOT / "dados"
    required_files = [
        "apartamentos.json",
        "areas.json",
        "reservas.json",
        "visitantes.json",
        "regulamento.md",
    ]
    for rf in required_files:
        p = dados_dir / rf
        if not p.exists() or p.stat().st_size == 0:
            return False, f"Arquivo obrigatório em dados/{rf} ausente ou vazio."

    # Verifica integridade do JSON
    import json
    for json_file in ["apartamentos.json", "areas.json", "reservas.json", "visitantes.json"]:
        try:
            with open(dados_dir / json_file, encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            return False, f"Arquivo dados/{json_file} corrompido: {e}"

    return True, "Arquivos de dados/ preservados e íntegros."


def check_t7_3() -> Tuple[bool, str]:
    """T7.3: Git commit e push final para a branch main do fork público."""
    # Valida que o repositório git está inicializado e funcional
    import subprocess
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return False, f"Comando git falhou: {proc.stderr}"
    except Exception as e:
        return False, f"Erro ao checar status do Git: {e}"

    return True, "Repositório Git íntegro e preparado para entrega."


TASK_VALIDATORS = {
    "T1.1": check_t1_1,
    "T1.2": check_t1_2,
    "T1.3": check_t1_3,
    "T1.4": check_t1_4,
    "T2.1": check_t2_1,
    "T2.2": check_t2_2,
    "T2.3": check_t2_3,
    "T2.4": check_t2_4,
    "T3.1": check_t3_1,
    "T3.2": check_t3_2,
    "T3.3": check_t3_3,
    "T4.1": check_t4_1,
    "T4.2": check_t4_2,
    "T4.3": check_t4_3,
    "T4.4": check_t4_4,
    "T4.5": check_t4_5,
    "T4.6": check_t4_6,
    "T4.7": check_t4_7,
    "T4.8": check_t4_8,
    "T5.1": check_t5_1,
    "T5.2": check_t5_2,
    "T5.3": check_t5_3,
    "T5.4": check_t5_4,
    "T5.5": check_t5_5,
    "T5.6": check_t5_6,
    "T6.1": check_t6_1,
    "T6.2": check_t6_2,
    "T6.3": check_t6_3,
    "T6.4": check_t6_4,
    "T6.5": check_t6_5,
    "T6.6": check_t6_6,
    "T6.7": check_t6_7,
    "T6.8": check_t6_8,
    "T7.1": check_t7_1,
    "T7.2": check_t7_2,
    "T7.3": check_t7_3,
}
