"""Shim de retrocompatibilidade. Redireciona para `ai_dm.domain.dungeon`."""

from ai_dm.domain.dungeon import (
    LOCK_TEMPLATES,
    ROOM_NAMES,
    DungeonMap,
    DungeonRoom,
    generate_dungeon_map,
    get_lock_status_text,
    render_map_svg,
)

__all__ = [
    "LOCK_TEMPLATES",
    "ROOM_NAMES",
    "DungeonMap",
    "DungeonRoom",
    "generate_dungeon_map",
    "get_lock_status_text",
    "render_map_svg",
]
