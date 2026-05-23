"""Eventos retornados pelo motor de jogo. UI traduz para mensagens."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameEvent:
    """Evento de jogo emitido pelo motor.

    Tipos comuns:
    - 'attack', 'damage', 'heal', 'miss', 'critical'
    - 'combat_start', 'combat_end_victory', 'combat_end_defeat'
    - 'level_up', 'xp_gain'
    - 'room_change', 'door_locked', 'door_unlocked'
    - 'narration' (texto livre do mestre)
    """

    type: str
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
