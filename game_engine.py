"""Shim de retrocompatibilidade. Redireciona para `ai_dm.domain` / `ai_dm.engine`."""

from __future__ import annotations

from ai_dm.domain.character import (
    ABILITY_FULL,
    ABILITY_NAMES,
    CLASS_DATA,
    RACE_DATA,
    Character,
    CharClass,
    Race,
    ability_modifier,
)
from ai_dm.domain.dice import RNG, roll, roll_check
from ai_dm.domain.monster import MONSTER_TEMPLATES, Monster, get_encounter_for_level
from ai_dm.engine.combat import (
    _single_attack,
    resolve_monster_attack,
    resolve_player_attack,
    use_potion,
)

__all__ = [
    "ABILITY_FULL",
    "ABILITY_NAMES",
    "CLASS_DATA",
    "MONSTER_TEMPLATES",
    "RACE_DATA",
    "RNG",
    "Character",
    "CharClass",
    "Monster",
    "Race",
    "_single_attack",
    "ability_modifier",
    "get_encounter_for_level",
    "resolve_monster_attack",
    "resolve_player_attack",
    "roll",
    "roll_check",
    "use_potion",
]
