#!/usr/bin/env python3
"""
CLI de Execução de Tarefas com Preservação de Contexto.
Projetado para permitir que agentes e desenvolvedores executem tarefas,
testes e validações sem poluir a janela de contexto com logs gigantescos.

Uso:
    python docs/task_runner.py status
    python docs/task_runner.py run <TASK_ID>
    python docs/task_runner.py run-phase <PHASE_NUM>
    python docs/task_runner.py exec "<COMANDO>"
    python docs/task_runner.py mark <TASK_ID> [done|todo]
    python docs/task_runner.py test [TEST_PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Adiciona raiz do projeto ao sys.path para importação consistente
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docs.routines.executor import run_quietly
from docs.routines.tasks_manager import TasksManager
from docs.routines.validators import TASK_VALIDATORS, run_pytest_quietly


def cmd_status(args, manager: TasksManager) -> int:
    print(manager.get_summary())
    pending = manager.list_pending(limit=3)
    if pending:
        print("\nPróximas pendentes:")
        for item in pending:
            print(f"  -> {item}")
    return 0


def cmd_run_task(args, manager: TasksManager) -> int:
    task_id = args.task_id.upper()
    validator = TASK_VALIDATORS.get(task_id)

    if not validator:
        print(f"[!] Validador automático para '{task_id}' ainda não implementado.")
        print(f"    Você pode marcar manualmente após executar: python docs/task_runner.py mark {task_id} done")
        return 1

    success, message = validator()
    if success:
        manager.mark_task(task_id, completed=True)
        print(f"[OK] Tarefa {task_id} validada com sucesso!")
        print(f"     Detalhe: {message}")
        print(f"     Status atualizado em docs/TASKS.md -> [x] **{task_id}**")
        return 0
    else:
        print(f"[FALHA] Tarefa {task_id} não passou na validação:")
        print(f"        Motivo: {message}")
        return 1


def cmd_run_phase(args, manager: TasksManager) -> int:
    phase_num = args.phase
    tasks = manager.parse_tasks()
    phase_tasks = [t for t in tasks if t.phase == phase_num]

    if not phase_tasks:
        print(f"[!] Nenhuma tarefa encontrada para a Fase {phase_num}.")
        return 1

    print(f"=== Executando validações da Fase {phase_num} ({len(phase_tasks)} tarefas) ===")
    all_ok = True
    for t in phase_tasks:
        validator = TASK_VALIDATORS.get(t.task_id)
        if validator:
            ok, msg = validator()
            if ok:
                manager.mark_task(t.task_id, completed=True)
                print(f"  [OK] {t.task_id}: {msg}")
            else:
                all_ok = False
                print(f"  [FALHA] {t.task_id}: {msg}")
        else:
            status_str = "[x] (já feita)" if t.completed else "[ ] (sem validador automático)"
            print(f"  [*] {t.task_id}: {status_str}")

    return 0 if all_ok else 1


def cmd_exec(args) -> int:
    cmd = args.command
    prefix = args.prefix or "exec"
    result = run_quietly(cmd, log_prefix=prefix)
    print(result.format_compact())
    return result.exit_code


def cmd_mark(args, manager: TasksManager) -> int:
    task_id = args.task_id.upper()
    done = args.status.lower() in ("done", "x", "true", "1")
    changed = manager.mark_task(task_id, completed=done)
    if changed:
        status_txt = "CONCLUÍDA [x]" if done else "PENDENTE [ ]"
        print(f"[OK] Tarefa {task_id} marcada como {status_txt} em docs/TASKS.md.")
        return 0
    else:
        print(f"[!] Tarefa {task_id} não encontrada em docs/TASKS.md.")
        return 1


def cmd_test(args) -> int:
    target = args.target
    result = run_pytest_quietly(target)
    print(result.format_compact())
    return result.exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rotinas de Execução e Validação de Tarefas (Zero Context Bloat)",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Mostra sumário do progresso das tarefas")
    p_status.set_defaults(func=cmd_status)

    # run
    p_run = subparsers.add_parser("run", help="Executa o validador de uma tarefa específica")
    p_run.add_argument("task_id", help="Identificador da tarefa (ex: T1.1, T1.2)")
    p_run.set_defaults(func=cmd_run_task)

    # run-phase
    p_phase = subparsers.add_parser("run-phase", help="Executa todas as validações de uma fase")
    p_phase.add_argument("phase", type=int, help="Número da fase (1 a 7)")
    p_phase.set_defaults(func=cmd_run_phase)

    # exec
    p_exec = subparsers.add_parser("exec", help="Executa comando silenciosamente salvando log completo")
    p_exec.add_argument("command", help="Comando a ser executado")
    p_exec.add_argument("--prefix", default=None, help="Prefixo para o arquivo de log")
    p_exec.set_defaults(func=cmd_exec)

    # mark
    p_mark = subparsers.add_parser("mark", help="Atualiza status de uma tarefa no docs/TASKS.md")
    p_mark.add_argument("task_id", help="ID da tarefa (ex: T2.1)")
    p_mark.add_argument("status", choices=["done", "todo"], help="Novo status")
    p_mark.set_defaults(func=cmd_mark)

    # test
    p_test = subparsers.add_parser("test", help="Roda o pytest de forma concisa")
    p_test.add_argument("target", nargs="?", default=None, help="Arquivo ou pasta de teste opcional")
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args()
    manager = TasksManager()

    if hasattr(args, "func"):
        if "manager" in args.func.__code__.co_varnames:
            return args.func(args, manager=manager)
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
