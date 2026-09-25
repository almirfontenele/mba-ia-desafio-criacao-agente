# Residencial Aurora — Assistente Virtual "Regra é Regra"

Assistente virtual para moradores do Residencial Aurora construído com **FastAPI** e **Google Agent Development Kit (ADK v2.2.0)**. O sistema gerencia reservas de áreas comuns (salão de festas, churrasqueira, quadra esportiva), cancelamentos, liberação de visitantes na portaria e esclarecimento de dúvidas sobre o regulamento interno do condomínio, aplicando rigorosamente o princípio: **"o modelo conduz a conversa, mas o código decide o que é permitido"**.

---

## 1. Arquitetura

O sistema adota uma arquitetura multiagente hierárquica baseada no padrão **Orchestrator-Specialists** do Google ADK, com persistência durável em SQLite (WAL mode) e desacoplamento total entre o raciocínio conversacional do LLM e as regras de domínio.

```
                      +-----------------------------------+
                      |       Morador / Cliente HTTP      |
                      +-----------------+-----------------+
                                        | (REST JSON)
                      +-----------------v-----------------+
                      |           FastAPI API             |
                      |   /sessoes  |  /apartamentos      |
                      +-----------------+-----------------+
                                        |
                      +-----------------v-----------------+
                      |       ADK Runtime & Runner        |
                      |    (SqliteSessionService - WAL)   |
                      +-----------------+-----------------+
                                        |
                      +-----------------v-----------------+
                      |      aurora_orchestrator          |
                      |       (Agente Principal)          |
                      +--------+--------+--------+--------+
                               |        |        |
            +------------------+        |        +------------------+
            |                           |                           |
+-----------v-----------+   +-----------v-----------+   +-----------v-----------+
|  reservas_specialist  |   | visitantes_specialist |   | regulamento_specialist|
|   (Subagente ADK)     |   |    (Subagente ADK)    |   |    (Subagente ADK)    |
+-----------+-----------+   +-----------+-----------+   +-----------+-----------+
            |                           |                           |
            | Tools com injeção estrita | Tools com injeção estrita | Ferramenta de busca
            | de context.state (Apto)   | de context.state (Apto)   | pontual de seções
            +-------------------+-------+-------+-------------------+
                                |               |
                      +---------v---------------v---------+
                      |       Camada de Domínio / DB      |
                      |     (SQLite WAL - Transações)     |
                      +-----------------------------------+
```

### Detalhamento dos Agentes

1. **`aurora_orchestrator` (Agente Principal)**:
   - **Arquivo**: `app/agents/orchestrator.py`
   - **Responsabilidade**: Atua como o concierge e recepcionista do condomínio. Recebe as mensagens do morador autenticado, mantém o fluxo da conversa agradável e delega as solicitações para os subagentes especialistas através de transfers do Google ADK.
   - **Como é acionado**: É o root agent registrado no `App` do ADK e acionado a cada turno de execução pelo `Runner.run_async(...)`.
   - **Por que existe**: Mantém as instruções do prompt principal enxutas e focadas em acolhimento e roteamento. O regulamento interno e regras de cobrança foram intencionalmente omitidos do seu prompt para prevenir alucinações e otimizar custos de contexto (Garantia 4).

2. **`reservas_specialist` (Especialista em Reservas)**:
   - **Arquivo**: `app/agents/specialists/reservas.py`
   - **Responsabilidade**: Gerencia o ciclo de vida das reservas de áreas comuns (quadra, salão de festas, churrasqueira). Responsável por checar disponibilidade de forma neutra, acionar solicitações de reserva, efetuar cancelamentos e listar reservas da própria unidade.
   - **Como é acionado**: Acionado via transfer automático do `aurora_orchestrator` quando o morador manifesta intenção de consultar, agendar ou cancelar reservas.
   - **Por que existe**: Isola o ferramental de agendamento em um subagente especializado equipado com as tools:
     - `checar_disponibilidade`: consulta neutra (sem expor morador).
     - `solicitar_reserva`: validação determinística de taxa (`> 0` gera confirmação, `== 0` grava direto).
     - `cancelar_minha_reserva`: cancela reservas do próprio apartamento sem confirmação.
     - `listar_minhas_reservas`: consulta restrita à própria unidade.

3. **`visitantes_specialist` (Especialista em Portaria e Visitantes)**:
   - **Arquivo**: `app/agents/specialists/visitantes.py`
   - **Responsabilidade**: Gerencia o controle de acesso e autorização de visitantes para a portaria do condomínio.
   - **Como é acionado**: Acionado pelo `aurora_orchestrator` quando o morador solicita autorização, liberação ou consulta de visitantes.
   - **Por que existe**: Garante que qualquer solicitação de entrada de terceiros passe obrigatoriamente pelo fluxo de confirmação prévia formal do sistema (Garantia 1), mesmo que o morador declare autorização direta no chat.

4. **`regulamento_specialist` (Especialista em Regulamento Interno)**:
   - **Arquivo**: `app/agents/specialists/regulamento.py`
   - **Responsabilidade**: Esclarece dúvidas sobre as regras de convivência do condomínio (horários da piscina, regras de mudança, animais, barulho, etc.).
   - **Como é acionado**: Acionado pelo `aurora_orchestrator` para perguntas institucionais e regulatórias.
   - **Por que existe**: Possui acesso exclusivo à tool `consultar_regulamento`. Em vez de reter o regulamento em sua instrução de sistema, pesquisa e extrai apenas a seção/artigo relevante em `dados/regulamento.md`, impedindo o vazamento de capítulos não relacionados nos eventos da sessão (Garantia 4).

---

## 2. Garantias do Sistema (Blindagem em Código)

As 5 garantias arquiteturais invioláveis são executadas diretamente pela lógica de domínio e pelo banco de dados, sendo 100% imunes a tentativas de engenharia de prompt ou ataques de injeção.

| Garantia | Descrição Curta | Arquivos Principais | Função / Trecho de Código |
|---|---|---|---|
| **Garantia 1** | Cobrança ou acesso só com confirmação | `app/domain/services.py`<br>`app/agents/tools/reservas_tools.py`<br>`app/agents/tools/visitantes_tools.py`<br>`app/api/routers/sessoes.py` | `criar_confirmacao_pendente`<br>`responder_confirmacao`<br>`solicitar_reserva` (linhas 69-86)<br>`solicitar_autorizacao_visitante` (linhas 29-45) |
| **Garantia 2** | Cada sessão pertence a um apartamento | `app/agents/tools/reservas_tools.py`<br>`app/agents/tools/visitantes_tools.py`<br>`app/domain/services.py`<br>`app/api/routers/sessoes.py` | `tool_context.state.get("apartamento")`<br>`cancelar_reserva_propria`<br>`listar_reservas_apartamento`<br>`consultar_disponibilidade_area` |
| **Garantia 3** | Nada se perde no reinício | `app/agents/runtime.py`<br>`app/database.py`<br>`app/main.py` | `get_session_service` (`SqliteSessionService`)<br>`get_db_connection` (`PRAGMA journal_mode = WAL`)<br>`lifespan` |
| **Garantia 4** | O regulamento é consultado, não carregado | `app/agents/orchestrator.py`<br>`app/agents/tools/regulamento_tools.py`<br>`app/agents/specialists/regulamento.py` | `aurora_orchestrator.instruction`<br>`consultar_regulamento`<br>`_carregar_secoes_regulamento` |
| **Garantia 5** | Dois moradores, uma reserva (Concorrência Atômica) | `app/database.py`<br>`app/domain/services.py` | `uq_reservas_area_data_ativa` (`UNIQUE INDEX`)<br>`immediate_transaction` (`BEGIN IMMEDIATE`)<br>`criar_reserva_atomica` |

---

### Detalhamento das Garantias

### Garantia 1: Cobrança ou Acesso Só com Confirmação
- **Localização no Código**:
  - `app/domain/services.py`: funções `criar_confirmacao_pendente`, `responder_confirmacao`, `executar_acao_confirmada`.
  - `app/agents/tools/reservas_tools.py`: função `solicitar_reserva`.
  - `app/agents/tools/visitantes_tools.py`: função `solicitar_autorizacao_visitante`.
  - `app/api/routers/sessoes.py`: rota `POST /sessoes/{session_id}/confirmacoes`.
- **Por que não depende do modelo**:
  O código inspeciona a taxa da área (`area.requer_confirmacao -> taxa > 0`) e o tipo de operação. Ao identificar cobrança (salão de festas ou churrasqueira) ou liberação de acesso na portaria, a tool não executa a gravação no banco; em vez disso, insere um registro na tabela `confirmacoes` com status `'PENDENTE'` e devolve o payload para o cliente HTTP em `confirmacoes_pendentes`. Mesmo que o morador diga no chat *"já confirmo aqui, pode liberar direto"*, nenhuma tool grava a autorização/reserva. Apenas uma chamada HTTP explícita em `POST /sessoes/{id}/confirmacoes` com `{"confirmado": true}` efetiva a ação. Caso receba um ID inexistente ou já respondido, a rota devolve status HTTP `409 Conflict` imediatamente.

### Garantia 2: Cada Sessão Pertence a um Apartamento
- **Localização no Código**:
  - `app/api/routers/sessoes.py`: rota `POST /sessoes` vincula `state={"apartamento": apto}`.
  - `app/agents/tools/reservas_tools.py` e `app/agents/tools/visitantes_tools.py`.
  - `app/domain/services.py`: funções `cancelar_reserva_propria`, `listar_reservas_apartamento`, `consultar_disponibilidade_area`.
- **Por que não depende do modelo**:
  O apartamento do morador é estabelecido uma única vez na criação da sessão e armazenado de forma imutável no estado interno do ADK (`session.state["apartamento"]`). Nenhuma ferramenta expõe o parâmetro `apartamento` na sua assinatura de parâmetros para o modelo Gemini; a tool obtém o número exclusivamente através de `tool_context.state["apartamento"]`. Tentativas de fingir ser outro apartamento ("Sou do 302, cancele a reserva dele") são totalmente frustradas: as rotas de cancelamento e listagem filtram `WHERE apartamento = ?`, e consultas de disponibilidade retornam apenas se a data está `livre` ou `ocupada`, sem jamais vazar códigos (`RSV-4821`) ou nomes (`Marina Duarte`).

### Garantia 3: Nada se Perde no Reinício
- **Localização no Código**:
  - `app/agents/runtime.py`: inicialização de `SqliteSessionService(db_path=DATABASE_PATH)` gravando em `aurora.db`.
  - `app/database.py`: configuração de banco de dados SQLite persistente em disco com `PRAGMA journal_mode = WAL` e `PRAGMA foreign_keys = ON`.
  - `app/main.py`: lifespan assíncrono que inicializa as tabelas na inicialização do servidor.
- **Por que não depende do modelo**:
  Todos os eventos de mensagens, histórico de conversas, estados de sessão do ADK, reservas, visitantes e confirmações são armazenados de forma durável no arquivo SQLite em disco (`aurora.db`). Quando a API é reiniciada (ou recriadas as instâncias de `App` e `Runner`), a sessão mantém sua integridade total, seu histórico integral é recuperável via `GET /sessoes/{id}/eventos` e novas mensagens continuam de onde a conversa parou.

### Garantia 4: O Regulamento é Consultado, Não Carregado
- **Localização no Código**:
  - `app/agents/orchestrator.py`: prompt de sistema do `aurora_orchestrator`.
  - `app/agents/tools/regulamento_tools.py`: funções `consultar_regulamento` e `_carregar_secoes_regulamento`.
  - `app/agents/specialists/regulamento.py`: subagente `regulamento_specialist`.
- **Por que não depende do modelo**:
  O prompt do orquestrador e dos agentes não embute o texto do regulamento. Ao receber uma dúvida sobre regras, o `regulamento_specialist` chama deterministicamente a função `consultar_regulamento(termo)`. Essa ferramenta lê `dados/regulamento.md`, fatiando-o em seções temáticas (capítulos e artigos), calcula a similaridade da consulta e devolve única e exclusivamente a seção de interesse (ex: artigo sobre funcionamento da piscina aos domingos). Nenhum capítulo estranho ou texto completo é adicionado aos eventos da sessão, preservando tokens e garantindo contexto limpo.

### Garantia 5: Dois Moradores, Uma Reserva (Concorrência Atômica)
- **Localização no Código**:
  - `app/database.py`: índice único parcial:
    ```sql
    CREATE UNIQUE INDEX IF NOT EXISTS uq_reservas_area_data_ativa 
    ON reservas(area, data) WHERE status = 'ATIVA';
    ```
    E gerenciadores de contexto com bloqueio imediato:
    ```python
    conn.execute("BEGIN IMMEDIATE")
    ```
  - `app/domain/services.py`: funções `criar_reserva_atomica` e `async_criar_reserva_atomica`.
- **Por que não depende do modelo**:
  A integridade não confia apenas em verificações prévias de leitura ("SELECT antes de INSERT"). A exclusividade é garantida no instante físico da gravação atômica: a transação é aberta com `BEGIN IMMEDIATE` e o SQLite impõe a restrição do índice único condicional para reservas com `status = 'ATIVA'`. Se dois moradores submeterem aprovação simultânea para a mesma área e data, uma transação obtém sucesso e a outra dispara imediatamente `sqlite3.IntegrityError`, sendo capturada de forma limpa pelo código de domínio e retornando HTTP 200 informativo de recusa sem qualquer falha de servidor (500) e sem duplicidade de reservas ativas.

---

## 3. Como Rodar

### Pré-requisitos
- **Python**: versão **3.12** ou superior (testado e homologado em Python 3.12 e 3.13).
- **Gerenciador de Pacotes**: `uv` instalado no ambiente.

### 1. Clonar e Configurar Variáveis de Ambiente
Copie o arquivo de variáveis de ambiente de exemplo e defina sua chave da API Google AI Studio:

```bash
cp .env.example .env
```

Edite o arquivo `.env`:
```env
GEMINI_API_KEY=sua_chave_do_google_ai_studio_aqui
DATABASE_PATH=aurora.db
```

### 2. Instalar Dependências com o `uv`
Execute a sincronização das dependências exatas fixadas no arquivo `uv.lock`:

```bash
uv sync
```

*(Caso utilize o Python global, pode-se invocar `python -m uv sync`)*.

### 3. Restaurar os Dados Iniciais
Para restaurar o banco de dados `aurora.db` ao estado original a partir dos arquivos JSON em `dados/`:

```bash
uv run python -m app.scripts.restore_data
```

### 4. Iniciar o Servidor FastAPI
Para iniciar a API em modo de produção/desenvolvimento respondendo na porta 8000:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

A API estará acessível em: `http://localhost:8000`.

### 5. Executar a Bateria Completa de Testes
Para rodar todos os testes automatizados do fluxo do avaliador (15 passos):

```bash
uv run pytest -v
```

---

## 4. Rotas da API Disponíveis

- `POST /sessoes`: Cria uma nova sessão associada a um apartamento (retorna `201` com `session_id`).
- `POST /sessoes/{session_id}/mensagens`: Envia mensagem no chat da sessão (retorna `200` com `resposta` e lista de `confirmacoes_pendentes`).
- `POST /sessoes/{session_id}/confirmacoes`: Responde a uma confirmação pendente (retorna `200` em caso de sucesso ou `409 Conflict` se ID for inválido ou repetido).
- `GET /sessoes/{session_id}/eventos`: Retorna o histórico sequencial integral de eventos gravados pelo ADK na sessão (`404` se sessão inexistente).
- `GET /apartamentos/{numero}/reservas`: Rota de auditoria que lista as reservas ativas do apartamento.
- `GET /apartamentos/{numero}/visitantes`: Rota de auditoria que lista os visitantes cadastrados para o apartamento.