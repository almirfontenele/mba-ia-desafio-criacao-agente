"""
Especialista em Reservas do Residencial Aurora (Google ADK).
Responsável por agendamento de áreas comuns, cancelamentos próprios e disponibilidade.
"""

from __future__ import annotations

from google.adk.agents import Agent

from app.agents.tools.reservas_tools import (
    cancelar_minha_reserva,
    checar_disponibilidade,
    listar_minhas_reservas,
    solicitar_reserva,
)

INSTRUCOES_RESERVAS = """
Você é o Especialista em Reservas do Residencial Aurora.
Sua responsabilidade é atender os moradores sobre reservas de áreas comuns:
- Salão de Festas (taxa R$ 150,00 - requer confirmação no aplicativo);
- Churrasqueira (taxa R$ 80,00 - requer confirmação no aplicativo);
- Quadra poliesportiva (gratuita - gravada imediatamente sem cobrança).

DIRETRIZES FUNDAMENTAIS:
1. Sempre utilize a ferramenta 'checar_disponibilidade' antes de prometer datas ao morador.
2. Ao solicitar uma reserva, acione 'solicitar_reserva'. Se a área possuir taxa, informe cordialmente o valor da taxa e explique que foi gerada uma solicitação de confirmação para ser aprovada na interface do aplicativo.
3. Se o morador pedir para cancelar, use 'cancelar_minha_reserva'. Você só pode cancelar reservas do próprio apartamento dele; a ferramenta cuida dessa restrição.
4. Para ver agendamentos da unidade, chame 'listar_minhas_reservas'.
5. Seja sempre prestativo, claro e educado.
"""

reservas_specialist = Agent(
    name="reservas_specialist",
    description="Especialista em consulta de disponibilidade, agendamento e cancelamento de reservas das áreas comuns do Residencial Aurora.",
    model="gemini-3.8-flash",
    instruction=INSTRUCOES_RESERVAS.strip(),
    tools=[
        checar_disponibilidade,
        solicitar_reserva,
        cancelar_minha_reserva,
        listar_minhas_reservas,
    ],
)
