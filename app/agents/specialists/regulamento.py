"""
Especialista em Regulamento Interno do Residencial Aurora (Google ADK).
Consulta pontual de artigos e regras específicas do condomínio (Garantia 4).
"""

from __future__ import annotations

from google.adk.agents import Agent

from app.agents.tools.regulamento_tools import consultar_regulamento

INSTRUCOES_REGULAMENTO = """
Você é o Especialista em Regulamento Interno do Residencial Aurora.
Sua missão é responder dúvidas dos moradores sobre normas, horários, barulho, mudanças, piscina e áreas comuns.

DIRETRIZES FUNDAMENTAIS:
1. Sempre consulte o regulamento utilizando a ferramenta 'consultar_regulamento' passando o tema da dúvida (ex: 'piscina', 'horário silêncio', 'mudança').
2. Responda de forma direta, clara e precisa com base exclusivamente no trecho retornado pela ferramenta.
3. Não invente regras nem extrapole o texto da consulta.
"""

regulamento_specialist = Agent(
    name="regulamento_specialist",
    description="Especialista nas normas, horários e artigos do regulamento interno do Residencial Aurora.",
    model="gemini-3.8-flash",
    instruction=INSTRUCOES_REGULAMENTO.strip(),
    tools=[
        consultar_regulamento,
    ],
)
