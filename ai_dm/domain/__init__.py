"""Domínio puro: regras de jogo sem dependências de UI ou LLM."""

from ai_dm.domain.dice import RNG, roll, roll_check
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
from ai_dm.domain.monster import MONSTER_TEMPLATES, Monster, get_encounter_for_level
from ai_dm.domain.dungeon import (
    LOCK_TEMPLATES,
    ROOM_NAMES,
    DungeonMap,
    DungeonRoom,
    generate_dungeon_map,
    get_lock_status_text,
    render_map_svg,
)
from ai_dm.domain.events import GameEvent

__all__ = [
    "RNG",
    "ABILITY_FULL",
    "ABILITY_NAMES",
    "CLASS_DATA",
    "RACE_DATA",
    "LOCK_TEMPLATES",
    "ROOM_NAMES",
    "MONSTER_TEMPLATES",
    "Character",
    "CharClass",
    "DungeonMap",
    "DungeonRoom",
    "GameEvent",
    "Monster",
    "Race",
    "ability_modifier",
    "generate_dungeon_map",
    "get_encounter_for_level",
    "get_lock_status_text",
    "render_map_svg",
    "roll",
    "roll_check",
]
