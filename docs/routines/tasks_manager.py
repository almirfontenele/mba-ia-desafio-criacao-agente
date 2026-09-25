"""
Gerenciador de tarefas integrado ao docs/TASKS.md.
Permite consultar e atualizar o progresso de tarefas de forma concisa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TASKS_MD_PATH = PROJECT_ROOT / "docs" / "TASKS.md"


@dataclass
class TaskItem:
    task_id: str
    phase: int
    title: str
    completed: bool
    line_number: int


class TasksManager:
    def __init__(self, tasks_file: Optional[Path] = None):
        self.tasks_file = tasks_file or TASKS_MD_PATH

    def parse_tasks(self) -> List[TaskItem]:
        if not self.tasks_file.exists():
            return []

        tasks: List[TaskItem] = []
        current_phase = 0
        task_regex = re.compile(r"^\s*-\s*\[([ xX])\]\s*\*\*([Tt]\d+\.\d+)\*\*:\s*(.+)$")
        phase_regex = re.compile(r"^#{2,4}\s*Fase\s*(\d+):", re.IGNORECASE)

        with open(self.tasks_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                phase_match = phase_regex.search(line)
                if phase_match:
                    current_phase = int(phase_match.group(1))
                    continue

                task_match = task_regex.search(line)
                if task_match:
                    check_mark = task_match.group(1).lower()
                    t_id = task_match.group(2).upper()
                    title = task_match.group(3).strip()
                    completed = check_mark == "x"
                    tasks.append(
                        TaskItem(
                            task_id=t_id,
                            phase=current_phase,
                            title=title,
                            completed=completed,
                            line_number=idx,
                        )
                    )

        return tasks

    def mark_task(self, task_id: str, completed: bool = True) -> bool:
        """Marca uma tarefa como concluída ou pendente no docs/TASKS.md."""
        target_id = task_id.upper()
        if not self.tasks_file.exists():
            return False

        with open(self.tasks_file, "r", encoding="utf-8") as f:
            content = f.read()

        new_status = "x" if completed else " "
        pattern = re.compile(
            rf"(-\s*\[)[ xX](\]\s*\*\*{re.escape(target_id)}\*\*:)", re.MULTILINE
        )

        new_content, count = pattern.subn(rf"\g<1>{new_status}\g<2>", content)
        if count > 0:
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True
        return False

    def get_summary(self) -> str:
        """Gera um sumário curto (2 a 4 linhas) do progresso para não encher o contexto."""
        tasks = self.parse_tasks()
        if not tasks:
            return "Nenhuma tarefa encontrada em docs/TASKS.md."

        total = len(tasks)
        completed = sum(1 for t in tasks if t.completed)
        pct = (completed / total * 100) if total > 0 else 0

        # Agrupamento por fase
        phases: Dict[int, List[TaskItem]] = {}
        for t in tasks:
            phases.setdefault(t.phase, []).append(t)

        phase_lines = []
        for phase_num in sorted(phases.keys()):
            p_tasks = phases[phase_num]
            p_done = sum(1 for t in p_tasks if t.completed)
            p_pct = (p_done / len(p_tasks) * 100) if p_tasks else 0
            phase_lines.append(f"Fase {phase_num}: {p_done}/{len(p_tasks)} ({p_pct:.0f}%)")

        summary = [
            f"=== Progresso Geral: {completed}/{total} tarefas concluídas ({pct:.1f}%) ===",
            " | ".join(phase_lines[:4]),
            " | ".join(phase_lines[4:]),
        ]
        return "\n".join([line for line in summary if line.strip()])

    def list_pending(self, limit: int = 5) -> List[str]:
        """Lista as próximas tarefas pendentes de forma concisa."""
        tasks = self.parse_tasks()
        pending = [f"[{t.task_id}] (Fase {t.phase}) {t.title[:80]}" for t in tasks if not t.completed]
        return pending[:limit]
