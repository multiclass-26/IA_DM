"""Persistência: serialização + migração com schema_version.

Correções v1.0:
- Nunca lê `gemini_api_key` do save (segurança / 12-Factor).
- `hp` é sempre clamped em [0, max_hp].
- Versão de esquema com migração futura.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ai_dm.domain.character import CharClass, Character, Race
from ai_dm.domain.dungeon import DungeonMap, DungeonRoom
from ai_dm.domain.monster import Monster

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Campos sensíveis NUNCA carregados de save.
SENSITIVE_KEYS = ("gemini_api_key",)


def serialize_character(char: Character | None) -> dict | None:
    if not char:
        return None
    return {
        "name": char.name,
        "race": char.race.name,
        "char_class": char.char_class.name,
        "level": char.level,
        "abilities": char.abilities,
        "hp": char.hp,
        "max_hp": char.max_hp,
        "ac": char.ac,
        "inventory": char.inventory,
        "gold": char.gold,
        "xp": char.xp,
        "special_uses": char.special_uses,
        "max_special_uses": char.max_special_uses,
        "conditions": char.conditions,
        "keys": char.keys,
    }


def deserialize_character(data: dict | None) -> Character | None:
    if not data:
        return None

    char = Character(
        name=data["name"],
        race=Race[data["race"]],
        char_class=CharClass[data["char_class"]],
    )
    char.level = int(data.get("level", char.level))
    char.abilities = data.get("abilities", char.abilities)
    char.max_hp = int(data.get("max_hp", char.max_hp))
    raw_hp = int(data.get("hp", char.hp))
    # Bug-fix v1.0: clamp em [0, max_hp].
    char.hp = max(0, min(raw_hp, char.max_hp))
    char.ac = int(data.get("ac", char.ac))
    char.inventory = list(data.get("inventory", char.inventory))
    char.gold = int(data.get("gold", char.gold))
    char.xp = int(data.get("xp", char.xp))
    char.special_uses = int(data.get("special_uses", char.special_uses))
    char.max_special_uses = int(data.get("max_special_uses", char.max_special_uses))
    char.conditions = list(data.get("conditions", char.conditions))
    char.keys = list(data.get("keys", char.keys))
    return char


def serialize_monster(monster: Monster) -> dict:
    return {
        "name": monster.name,
        "hp": monster.hp,
        "max_hp": monster.max_hp,
        "ac": monster.ac,
        "attack_bonus": monster.attack_bonus,
        "damage": monster.damage,
        "xp_reward": monster.xp_reward,
        "description": monster.description,
        "special": monster.special,
    }


def deserialize_monster(data: dict) -> Monster:
    return Monster(
        name=data["name"],
        hp=int(data["hp"]),
        max_hp=int(data["max_hp"]),
        ac=int(data["ac"]),
        attack_bonus=int(data["attack_bonus"]),
        damage=data["damage"],
        xp_reward=int(data["xp_reward"]),
        description=data.get("description", ""),
        special=data.get("special", ""),
    )


def serialize_dungeon_map(dmap: DungeonMap | None) -> dict | None:
    if not dmap:
        return None
    return {
        "current_room": dmap.current_room,
        "locks": dmap.locks,
        "rooms": [
            {
                "number": room.number,
                "room_type": room.room_type,
                "name": room.name,
                "connections": room.connections,
                "explored": room.explored,
                "locked": room.locked,
                "lock_info": room.lock_info,
                "has_key": room.has_key,
            }
            for room in dmap.rooms
        ],
    }


def deserialize_dungeon_map(data: dict | None) -> DungeonMap | None:
    if not data:
        return None
    rooms = [
        DungeonRoom(
            number=room["number"],
            room_type=room["room_type"],
            name=room["name"],
            connections=list(room.get("connections", [])),
            explored=bool(room.get("explored", False)),
            locked=bool(room.get("locked", False)),
            lock_info=dict(room.get("lock_info", {})),
            has_key=room.get("has_key", ""),
        )
        for room in data.get("rooms", [])
    ]
    return DungeonMap(
        rooms=rooms,
        locks=list(data.get("locks", [])),
        current_room=int(data.get("current_room", 1)),
    )


def migrate(payload: dict) -> dict:
    """Migra um save antigo para o esquema atual."""
    version = int(payload.get("schema_version", 0))
    if version == SCHEMA_VERSION:
        return payload

    # v0 -> v1: dropar gemini_api_key se presente.
    for key in SENSITIVE_KEYS:
        if key in payload:
            log.info("Removendo campo sensivel %r do save (migracao v0->v1).", key)
            payload.pop(key, None)
    # Default model migration.
    if payload.get("gemini_model") in (None, "", "gemini-2.0-flash"):
        payload["gemini_model"] = "gemini-2.5-flash-lite"

    payload["schema_version"] = SCHEMA_VERSION
    return payload


def write_save(path: Path, payload: dict) -> None:
    payload = dict(payload)
    # Nunca grave segredos.
    for key in SENSITIVE_KEYS:
        payload.pop(key, None)
    payload["schema_version"] = SCHEMA_VERSION
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def read_save(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return migrate(raw)
