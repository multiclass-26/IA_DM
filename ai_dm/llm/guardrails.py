"""Guardrails: detectar saída inadequada da LLM e classificar combate."""

from __future__ import annotations

import re

# Termos que indicam que a IA está fazendo matemática de combate por conta
# própria (proibido — o motor controla isso). Lista mais conservadora que a
# regex original para reduzir falsos positivos em narrativa não-combate.
_FORBIDDEN_PATTERNS = [
    re.compile(r"\bd\s*20\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*d\s*\d+\s*[+\-]?\s*\d*\b"),
    re.compile(r"\brolagem\b", re.IGNORECASE),
    re.compile(r"\b(critico|cr[ií]tica)\b", re.IGNORECASE),
    re.compile(r"\bdano\s*[:=]\s*\d+", re.IGNORECASE),
    re.compile(r"\bHP\s*[:=]?\s*\d+\s*/\s*\d+", re.IGNORECASE),
    re.compile(r"\bCA\s*[:=]?\s*\d+", re.IGNORECASE),
    re.compile(r"\bturno\s+(do|de|da)\b", re.IGNORECASE),
]

# Termos que sinalizam intenção de iniciar combate na narrativa.
_COMBAT_KEYWORDS = [
    "ataca", "ataque", "investe", "avanca", "avancam", "se prepara para lutar",
    "saca", "saque", "saca a arma", "rosna", "rosnado",
    "iniciativa", "iniciar combate", "combate comeca",
    "se lanca", "se lancam", "se atira", "surge", "surgem",
    "preparam-se", "se preparam", "se erguem",
]


def contains_manual_combat_math(text: str) -> bool:
    """Retorna True se a IA tentou fazer rolagem/dano/HP manualmente."""
    if not text:
        return False
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(text):
            return True
    return False


def looks_like_combat_start(text: str) -> bool:
    """Heurística simples: parece que o texto está iniciando um combate?"""
    if not text:
        return False
    lower = text.lower()
    return any(kw in lower for kw in _COMBAT_KEYWORDS)
