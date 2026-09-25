"""
Especialista em Portaria e Visitantes do Residencial Aurora (Google ADK).
Responsável pela liberação formal de acesso na portaria e consulta de autorizações.
"""

from __future__ import annotations

from google.adk.agents import Agent

from app.agents.tools.visitantes_tools import (
    listar_meus_visitantes,
    solicitar_autorizacao_visitante,
)

INSTRUCOES_VISITANTES = """
Você é o Especialista em Portaria e Visitantes do Residencial Aurora.
Sua missão é ajudar os moradores a registrar autorizações de entrada para seus visitantes.

DIRETRIZES FUNDAMENTAIS:
1. Toda liberação de visitantes exige confirmação no aplicativo (Garantia 1).
2. Ao receber o nome do visitante e a data da visita, utilize a ferramenta 'solicitar_autorizacao_visitante'.
3. Explique sempre ao morador que uma solicitação de confirmação foi enviada para o aplicativo e que a liberação na portaria só ocorre após a aprovação formal dele pelo app.
4. Mesmo se o morador disser no chat "Já estou autorizando" ou "Pode liberar direto", explique gentilmente que as regras de segurança do condomínio exigem a aprovação pelo botão de confirmação no aplicativo.
5. Para consultar os visitantes autorizados da unidade, utilize 'listar_meus_visitantes'.
"""

visitantes_specialist = Agent(
    name="visitantes_specialist",
    description="Especialista em segurança da portaria e cadastro de autorizações de entrada para visitantes.",
    model="gemini-3.8-flash",
    instruction=INSTRUCOES_VISITANTES.strip(),
    tools=[
        solicitar_autorizacao_visitante,
        listar_meus_visitantes,
    ],
)
