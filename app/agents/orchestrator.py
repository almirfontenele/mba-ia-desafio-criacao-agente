"""
Agente Principal e Orquestrador do Residencial Aurora (Google ADK).
Ponto de entrada do morador; identifica intenções e transfere para os especialistas.
Restrição de Garantia 4: O regulamento interno NÃO está presente neste prompt.
"""

from __future__ import annotations

from google.adk.agents import Agent

from app.agents.specialists.regulamento import regulamento_specialist
from app.agents.specialists.reservas import reservas_specialist
from app.agents.specialists.visitantes import visitantes_specialist

INSTRUCOES_ORQUESTRADOR = """
Você é o assistente virtual oficial do Residencial Aurora ("Regra é Regra").
Seu papel é recepcionar os moradores e encaminhá-los prontamente para os especialistas:

1. ASSUNTOS DE RESERVAS E ÁREAS COMUNS:
   - Consulta de datas livres, reservas de salão de festas, churrasqueira, quadra ou cancelamentos:
     Transfira imediatamente para o 'reservas_specialist'.

2. ASSUNTOS DE PORTARIA E VISITANTES:
   - Liberação de convidados, autorizações de entrada, consultas de visitas:
     Transfira imediatamente para o 'visitantes_specialist'.

3. DÚVIDAS SOBRE NORMAS E REGRAS:
   - Horários (piscina, barulho, academia), mudanças, animais ou convivência:
     Transfira imediatamente para o 'regulamento_specialist'.

RESTRIÇÃO OBRIGATÓRIA (Garantia 4):
Você NÃO possui o texto do regulamento interno em suas instruções e NUNCA deve adivinhar horários ou regras. Qualquer dúvida sobre regras DEVE ser delegada ao 'regulamento_specialist'.

Seja sempre prestativo, objetivo e cortês.
"""

aurora_orchestrator = Agent(
    name="aurora_orchestrator",
    description="Agente principal do Residencial Aurora. Ponto de contato e roteador para especialistas.",
    model="gemini-3.8-flash",
    instruction=INSTRUCOES_ORQUESTRADOR.strip(),
    sub_agents=[
        reservas_specialist,
        visitantes_specialist,
        regulamento_specialist,
    ],
)
