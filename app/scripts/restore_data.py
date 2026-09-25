"""
Script de restauração fiel dos dados do condomínio Residencial Aurora.
Lê os arquivos imutáveis em dados/ e recria o banco de dados no estado inicial da avaliação.

Uso:
    python -m app.scripts.restore_data
    # ou
    uv run python -m app.scripts.restore_data
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import get_db_connection, get_db_path, init_db


def restore_initial_data(db_path: Optional[Union[Path, str]] = None) -> None:
    """Restaura as tabelas e dados iniciais de dados/*.json no banco SQLite."""
    target_path = get_db_path(db_path)
    dados_dir = PROJECT_ROOT / "dados"

    # 1. Garante schema e tabelas criadas
    init_db(target_path)

    # 2. Carrega arquivos JSON
    with open(dados_dir / "apartamentos.json", "r", encoding="utf-8") as f:
        apartamentos_data = json.load(f)

    with open(dados_dir / "areas.json", "r", encoding="utf-8") as f:
        areas_data = json.load(f)

    with open(dados_dir / "reservas.json", "r", encoding="utf-8") as f:
        reservas_data = json.load(f)

    with open(dados_dir / "visitantes.json", "r", encoding="utf-8") as f:
        visitantes_data = json.load(f)

    # 3. Limpa e recarrega os dados em transação única
    with get_db_connection(target_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Limpa tabelas na ordem de dependência reversa
            conn.execute("DELETE FROM confirmacoes;")
            conn.execute("DELETE FROM reservas;")
            conn.execute("DELETE FROM visitantes;")
            conn.execute("DELETE FROM apartamentos;")
            conn.execute("DELETE FROM areas;")

            # Insere apartamentos
            conn.executemany(
                "INSERT INTO apartamentos (numero, morador) VALUES (?, ?)",
                [(item["numero"], item["morador"]) for item in apartamentos_data],
            )

            # Insere áreas
            conn.executemany(
                "INSERT INTO areas (id, nome, taxa) VALUES (?, ?, ?)",
                [(item["id"], item["nome"], float(item.get("taxa", 0.0))) for item in areas_data],
            )

            # Insere reservas pré-existentes
            conn.executemany(
                "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, 'ATIVA')",
                [(item["codigo"], item["apartamento"], item["area"], item["data"]) for item in reservas_data],
            )

            # Insere visitantes pré-existentes
            conn.executemany(
                "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
                [(item["apartamento"], item["nome"], item["data"]) for item in visitantes_data],
            )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def main() -> int:
    print("Iniciando restauração dos dados do Residencial Aurora...")
    try:
        restore_initial_data()
        target = get_db_path()
        print(f"[OK] Banco de dados restaurado com sucesso em: {target}")
        return 0
    except Exception as e:
        print(f"[ERRO] Falha ao restaurar dados: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
