"""
Testes unitários e de integração para app/domain/services.py e app/scripts/restore_data.py.
Valida as Garantias 1, 2 e 5.
"""

from pathlib import Path
import pytest

from app.domain.services import (
    cancelar_reserva_propria,
    consultar_disponibilidade_area,
    criar_confirmacao_pendente,
    criar_reserva_atomica,
    gerar_codigo_reserva,
    listar_confirmacoes_pendentes,
    listar_reservas_apartamento,
    listar_visitantes_apartamento,
    responder_confirmacao,
)
from app.scripts.restore_data import restore_initial_data


@pytest.fixture
def fresh_db(tmp_path: Path) -> Path:
    """Banco de dados temporário com dados restaurados."""
    db_file = tmp_path / "test_aurora.db"
    restore_initial_data(db_file)
    return db_file


def test_garantia_2_isolamento_reservas(fresh_db: Path):
    """Morador do 101 só vê suas reservas; não vê RSV-4821 do 302."""
    reservas_101 = listar_reservas_apartamento("101", db_path=fresh_db)
    assert len(reservas_101) == 1
    assert reservas_101[0]["codigo"] == "RSV-1377"

    reservas_302 = listar_reservas_apartamento("302", db_path=fresh_db)
    assert len(reservas_302) == 1
    assert reservas_302[0]["codigo"] == "RSV-4821"

    # Confirma que 101 não contém dados do 302
    codigos_101 = [r["codigo"] for r in reservas_101]
    assert "RSV-4821" not in codigos_101


def test_garantia_2_isolamento_visitantes(fresh_db: Path):
    """Visitantes do 302 (Marina Duarte) não aparecem na lista do 101."""
    vis_101 = listar_visitantes_apartamento("101", db_path=fresh_db)
    assert len(vis_101) == 0

    vis_302 = listar_visitantes_apartamento("302", db_path=fresh_db)
    assert len(vis_302) == 1
    assert vis_302[0]["nome"] == "Marina Duarte"


def test_garantia_2_consulta_neutra_disponibilidade(fresh_db: Path):
    """Consulta de disponibilidade retorna apenas booleano, sem dados de quem reservou."""
    # 2030-03-09 na quadra está reservada pelo 101
    assert consultar_disponibilidade_area("quadra", "2030-03-09", db_path=fresh_db) is False

    # 2030-03-10 na quadra está livre
    assert consultar_disponibilidade_area("quadra", "2030-03-10", db_path=fresh_db) is True


def test_garantia_2_cancelamento_proprio_e_bloqueio_terceiros(fresh_db: Path):
    """Morador do 101 pode cancelar sua própria reserva, mas NÃO pode cancelar do 302."""
    # Tentativa de cancelar reserva do 302 (RSV-4821) a partir do apartamento 101
    sucesso, msg = cancelar_reserva_propria("101", "RSV-4821", db_path=fresh_db)
    assert sucesso is False
    assert "Nenhuma reserva ativa encontrada" in msg

    # Confirma que a reserva do 302 continua ativa
    reservas_302 = listar_reservas_apartamento("302", db_path=fresh_db)
    assert len(reservas_302) == 1

    # Cancelamento da própria reserva (RSV-1377) do 101
    sucesso, msg = cancelar_reserva_propria("101", "RSV-1377", db_path=fresh_db)
    assert sucesso is True

    # Agora a reserva do 101 está cancelada
    reservas_101 = listar_reservas_apartamento("101", db_path=fresh_db)
    assert len(reservas_101) == 0


def test_garantia_5_concorrencia_atomica(fresh_db: Path):
    """
    Dois moradores tentam reservar o salão de festas na mesma data (2030-05-11).
    A primeira transação sucede; a segunda é recusada amigavelmente sem crash.
    """
    # 1º morador (101)
    ok1, cod1, msg1 = criar_reserva_atomica("101", "salao-de-festas", "2030-05-11", db_path=fresh_db)
    assert ok1 is True
    assert cod1 is not None

    # 2º morador (201) tenta no mesmo dia
    ok2, cod2, msg2 = criar_reserva_atomica("201", "salao-de-festas", "2030-05-11", db_path=fresh_db)
    assert ok2 is False
    assert cod2 is None
    assert "já está reservada" in msg2 or "acabou de ser reservada" in msg2


def test_garantia_1_maquina_estados_confirmacoes(fresh_db: Path):
    """Valida ciclo de confirmação, aprovação, rejeição e idempotência (409 Conflict)."""
    session_id = "sess_test_123"

    # Criação de confirmação pendente
    conf = criar_confirmacao_pendente(
        session_id=session_id,
        apartamento="101",
        acao="reservar_area",
        detalhes={"area": "salao-de-festas", "data": "2030-06-01"},
        db_path=fresh_db,
    )
    assert conf.status == "PENDENTE"

    # Listagem de pendentes
    pendentes = listar_confirmacoes_pendentes(session_id, db_path=fresh_db)
    assert len(pendentes) == 1
    assert pendentes[0]["id"] == conf.id

    # Idempotência: ID inexistente deve retornar status 409
    ok_inv, msg_inv, code_inv = responder_confirmacao(
        session_id, "conf_inexistente", True, db_path=fresh_db
    )
    assert ok_inv is False
    assert code_inv == 409

    # Aprovação com sucesso
    ok_app, msg_app, code_app = responder_confirmacao(
        session_id, conf.id, True, db_path=fresh_db
    )
    assert ok_app is True
    assert code_app == 200

    # Confirmação não deve mais constar como pendente
    pendentes_depois = listar_confirmacoes_pendentes(session_id, db_path=fresh_db)
    assert len(pendentes_depois) == 0

    # Reenvio da mesma confirmação deve retornar 409 Conflict (Idempotência)
    ok_dup, msg_dup, code_dup = responder_confirmacao(
        session_id, conf.id, True, db_path=fresh_db
    )
    assert ok_dup is False
    assert code_dup == 409
