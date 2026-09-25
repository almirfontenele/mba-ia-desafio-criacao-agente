# Rotinas de Execução e Validação de Tarefas (Zero Context Bloat)

Este diretório contém utilitários Python desenvolvidos especialmente para executar tarefas, testes e validações do projeto **sem poluir a janela de contexto de agentes de IA**.

---

## 1. Por que estas rotinas existem?

Durante o desenvolvimento agentic e testes intensivos (como a bateria de 15 passos do avaliador), comandos de terminal podem produzir centenas ou milhares de linhas de saída (logs de compilação, traceback, stdout de testes, requests HTTP). 

Inserir toda essa saída no prompt da conversa consome a janela de contexto, aumenta custos e pode causar degradação do raciocínio (*context degradation*).

**Solução implementada**:
- Todo comando roda de forma silenciosa e controlada.
- A saída integral é sempre preservada em disco em `.task_logs/<prefixo>_<timestamp>.log`.
- No terminal / contexto da conversa, é emitido apenas um **sumário conciso (1 a 4 linhas)** com o status, tempo de execução e, em caso de erro, apenas as últimas linhas críticas.

---

## 2. Estrutura dos Arquivos

```text
docs/
├── task_runner.py          # CLI principal para executar tarefas e comandos
├── routines/
│   ├── __init__.py
│   ├── executor.py         # Subprocess runner silencioso e gerador de sumários
│   ├── tasks_manager.py    # Parser e atualizador automático de docs/TASKS.md
│   └── validators.py       # Validadores programáticos de cada fase/tarefa
├── ROUTINES.md             # Esta documentação
├── TASKS.md                # Matriz e checklist de tarefas do projeto
├── SPEC.md                 # Especificação técnica completa
└── PRD.md                  # Requisitos de produto
```

---

## 3. Guia de Comandos da CLI (`docs/task_runner.py`)

### 3.1 Ver o Progresso Geral (`status`)
Mostra um resumo de 3 a 5 linhas do progresso de cada fase e as próximas tarefas pendentes:
```bash
python docs/task_runner.py status
```
*Exemplo de saída:*
```text
=== Progresso Geral: 4/36 tarefas concluídas (11.1%) ===
Fase 1: 4/4 (100%) | Fase 2: 0/4 (0%) | Fase 3: 0/3 (0%) | Fase 4: 0/8 (0%)
Fase 5: 0/6 (0%) | Fase 6: 0/8 (0%) | Fase 7: 0/3 (0%)

Próximas pendentes:
  -> [T2.1] (Fase 2) Implementar app/database.py com suporte a SQLite durável em disco
```

### 3.2 Executar e Validar uma Tarefa (`run`)
Executa o validador automatizado da tarefa. Se aprovada, atualiza automaticamente o status no `docs/TASKS.md` (`- [ ]` -> `- [x]`):
```bash
python docs/task_runner.py run T1.1
```

### 3.3 Validar uma Fase Completa (`run-phase`)
Executa todas as validações de uma fase específica:
```bash
python docs/task_runner.py run-phase 1
```

### 3.4 Executar Comandos de Terminal Silenciosamente (`exec`)
Executa qualquer comando de shell, gravando o log integral em `.task_logs/` e retornando apenas o sumário:
```bash
python docs/task_runner.py exec "uv sync"
python docs/task_runner.py exec "uv run uvicorn app.main:app --port 8000" --prefix server
```

### 3.5 Executar Testes Pytest de Forma Concisa (`test`)
Executa a suíte de testes gravando todo o traceback em disco e exibindo apenas a linha de sumário do pytest:
```bash
python docs/task_runner.py test
# Ou testando um arquivo específico:
python docs/task_runner.py test tests/test_avaliador_flow.py
```

### 3.6 Marcar Tarefa Manualmente (`mark`)
Altera o status de uma tarefa no `docs/TASKS.md` sem abrir ou editar manualmente o arquivo:
```bash
python docs/task_runner.py mark T2.1 done
python docs/task_runner.py mark T2.1 todo
```

---

## 4. Onde Encontrar os Logs Completos?

Todos os logs detalhados são armazenados no diretório `.task_logs/` na raiz do projeto (devidamente ignorado pelo Git):
```text
.task_logs/
├── exec_20260925_154832.log
├── pytest_20260925_155010.log
└── ...
```
Quando for necessário inspecionar um erro profundo, basta consultar o arquivo de log indicado na saída do comando.
