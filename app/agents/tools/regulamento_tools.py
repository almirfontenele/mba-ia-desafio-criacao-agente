"""
Ferramenta pontual de consulta ao regulamento interno do condomínio (Garantia 4).
Segmenta dados/regulamento.md e retorna exclusivamente o trecho/capítulo pertinente,
evitando poluir a janela de contexto ou os eventos da sessão com textos não correlacionados.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from google.adk.tools import ToolContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REGULAMENTO_PATH = PROJECT_ROOT / "dados" / "regulamento.md"

_CHAPTERS_CACHE: Optional[List[Dict[str, str]]] = None


def _carregar_capitulos() -> List[Dict[str, str]]:
    """Lê e segmenta o regulamento em capítulos com palavras-chave associadas."""
    global _CHAPTERS_CACHE
    if _CHAPTERS_CACHE is not None:
        return _CHAPTERS_CACHE

    if not REGULAMENTO_PATH.exists():
        return []

    conteudo = REGULAMENTO_PATH.read_text(encoding="utf-8")
    partes = re.split(r"(?m)^##\s+", conteudo)

    capitulos: List[Dict[str, str]] = []
    for parte in partes:
        if not parte.strip():
            continue
        linhas = parte.strip().splitlines()
        titulo = linhas[0].strip()
        corpo = "\n".join(linhas[1:]).strip()

        capitulos.append({
            "titulo": titulo,
            "texto": f"## {titulo}\n\n{corpo}",
            "busca": f"{titulo.lower()} {corpo.lower()}",
        })

    _CHAPTERS_CACHE = capitulos
    return capitulos


def consultar_regulamento(topico: str) -> str:
    """
    Consulta pontual ao regulamento interno do Residencial Aurora.
    Retorna apenas a seção ou capítulo diretamente relacionado ao tema consultado.
    
    Args:
        topico: Tema, dúvida ou palavra-chave (ex: 'piscina', 'barulho', 'mudança', 'animais', 'horário salão').
    """
    capitulos = _carregar_capitulos()
    if not capitulos:
        return "Regulamento interno indisponível no momento."

    termos = [t.lower().strip() for t in re.split(r"\W+", topico) if len(t) >= 3]
    if not termos:
        return "Por favor, especifique o assunto do regulamento que deseja consultar."

    # Pontuação por correspondência de termos no título e no corpo
    melhor_capitulo = None
    maior_score = 0

    for cap in capitulos:
        score = 0
        titulo_lower = cap["titulo"].lower()
        texto_lower = cap["busca"]

        for termo in termos:
            # Termo no título tem peso muito maior
            if termo in titulo_lower:
                score += 10
            # Termo no corpo
            if termo in texto_lower:
                score += 1 + texto_lower.count(termo)

        if score > maior_score:
            maior_score = score
            melhor_capitulo = cap

    if melhor_capitulo and maior_score > 0:
        return melhor_capitulo["texto"]

    return (
        f"Não foram encontradas normas específicas sobre '{topico}' no regulamento. "
        "Consulte a administração pelo aplicativo para mais detalhes."
    )
