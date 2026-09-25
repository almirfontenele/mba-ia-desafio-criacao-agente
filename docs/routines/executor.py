"""
Executor de comandos silencioso para preservação de contexto de LLM.
Redireciona saídas extensas para arquivos de log em disco (.task_logs/)
e retorna apenas sumários concisos para a tela.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PROJECT_ROOT / ".task_logs"


@dataclass
class ExecutionResult:
    command: str
    exit_code: int
    duration_seconds: float
    log_file: Path
    stdout_summary: str
    error_snippet: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def format_compact(self) -> str:
        """Retorna uma representação ultracompacta para não poluir o contexto."""
        status_icon = "[OK]" if self.success else "[FALHA]"
        log_rel = os.path.relpath(self.log_file, PROJECT_ROOT)
        
        lines = [
            f"{status_icon} '{self.command}' (código {self.exit_code}, {self.duration_seconds:.2f}s)",
            f"  Log completo gravado em: {log_rel}",
        ]
        if self.stdout_summary:
            lines.append(f"  Sumário: {self.stdout_summary}")
            
        if not self.success and self.error_snippet:
            lines.append("  Detalhe do Erro (últimas linhas):")
            for err_line in self.error_snippet.strip().splitlines()[-10:]:
                lines.append(f"    | {err_line}")
                
        return "\n".join(lines)


def ensure_logs_dir() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def run_quietly(
    cmd: Union[str, List[str]],
    log_prefix: str = "task",
    cwd: Optional[Path] = None,
    env_vars: Optional[dict] = None,
    timeout: int = 300,
) -> ExecutionResult:
    """
    Executa um comando de terminal salvando a saída integral em arquivo de log.
    Retorna apenas um sumário resumido da execução.
    """
    ensure_logs_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = "".join(c if c.isalnum() or c in "-_" else "_" for c in log_prefix)
    log_path = LOGS_DIR / f"{safe_prefix}_{timestamp}.log"

    work_dir = cwd or PROJECT_ROOT
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    shell_mode = isinstance(cmd, str) and (sys.platform == "win32" or " " in cmd)

    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            shell=shell_mode,
            cwd=str(work_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        duration = time.time() - start_time
        exit_code = proc.returncode
        full_output = proc.stdout or ""
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        exit_code = -1
        full_output = (e.stdout or "") + f"\n[ERRO: Comando expirou após {timeout}s]"
    except Exception as e:
        duration = time.time() - start_time
        exit_code = -2
        full_output = f"[ERRO ao disparar comando]: {str(e)}"

    # Salva log integral em disco
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"=== COMANDO: {cmd_str} ===\n")
        f.write(f"=== DATA: {datetime.now().isoformat()} ===\n")
        f.write(f"=== DIRETORIO: {work_dir} ===\n")
        f.write(f"=== STATUS: {exit_code} ===\n")
        f.write(f"=== TEMPO: {duration:.2f}s ===\n\n")
        f.write(full_output)

    # Extrai sumário inteligente dependendo da ferramenta
    summary = _extract_summary(cmd_str, full_output, exit_code)
    error_snippet = None
    if exit_code != 0:
        error_snippet = _extract_error_snippet(full_output)

    return ExecutionResult(
        command=cmd_str,
        exit_code=exit_code,
        duration_seconds=duration,
        log_file=log_path,
        stdout_summary=summary,
        error_snippet=error_snippet,
    )


def _extract_summary(command: str, output: str, exit_code: int) -> str:
    """Gera uma linha de sumário limpa baseada na ferramenta executada."""
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    if not lines:
        return "Sem saída gerada."

    # Sumário Pytest
    if "pytest" in command:
        for line in reversed(lines):
            if "passed" in line or "failed" in line or "error" in line:
                return line
        return lines[-1] if lines else "Execução pytest concluída."

    # Sumário uv sync
    if "uv sync" in command or "uv pip" in command:
        for line in lines:
            if "Installed" in line or "Audited" in line or "Resolved" in line:
                return line
        return lines[-1]

    # Sumário Uvicorn / Server
    if "uvicorn" in command:
        for line in lines:
            if "Uvicorn running on" in line or "Application startup complete" in line:
                return line
        return lines[-1]

    # Padrão: última linha não vazia
    return lines[-1][:120]


def _extract_error_snippet(output: str, max_lines: int = 10) -> str:
    """Extrai apenas as últimas linhas relevantes de erro."""
    lines = [l for l in output.splitlines() if l.strip()]
    return "\n".join(lines[-max_lines:])
