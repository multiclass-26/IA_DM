"""Testa guardrails de combate-math e detecção de início de combate."""

import pytest

from ai_dm.llm.guardrails import contains_manual_combat_math, looks_like_combat_start


@pytest.mark.parametrize(
    "text",
    [
        "Voce rola um d20+5 contra a CA do goblin.",
        "Dano: 12. HP: 5/15.",
        "Rolagem de dano: 2d8+3",
        "Acerto critico!",
    ],
)
def test_detects_combat_math(text):
    assert contains_manual_combat_math(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Voce entra no salao. O ar e gelido.",
        "Um homem encapuzado oferece informacoes.",
        "Voce encontra 30 moedas de ouro.",
    ],
)
def test_clean_narrative_ok(text):
    assert contains_manual_combat_math(text) is False


def test_detects_combat_start():
    assert looks_like_combat_start("O goblin ataca voce!")
    assert looks_like_combat_start("Dois ogros avancam ferozmente.")


def test_no_combat_start_in_pure_exploration():
    assert not looks_like_combat_start("Voce examina a mesa empoeirada.")
