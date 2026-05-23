"""Motor de jogo: combate e exploração (sem dependências de UI/LLM)."""

from ai_dm.engine.combat import (
    resolve_monster_attack,
    resolve_player_attack,
    use_potion,
)

__all__ = ["resolve_monster_attack", "resolve_player_attack", "use_potion"]
