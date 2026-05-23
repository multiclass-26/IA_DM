"""Persistência: roundtrip + segurança (não carregar API key) + clamp HP."""

import json
from pathlib import Path

import pytest

from ai_dm.domain.character import Character, CharClass, Race
from ai_dm.persistence import save as save_mod
from ai_dm.persistence.save import (
    SCHEMA_VERSION,
    deserialize_character,
    migrate,
    read_save,
    serialize_character,
    write_save,
)


def test_character_roundtrip():
    original = Character(name="Aelin", race=Race.ELFO, char_class=CharClass.LADINO)
    original.gain_xp(900)  # nivel 3
    original.add_key("Gema de Sangue")
    original.gold = 137

    data = serialize_character(original)
    restored = deserialize_character(data)

    assert restored is not None
    assert restored.name == original.name
    assert restored.race == original.race
    assert restored.char_class == original.char_class
    assert restored.level == original.level
    assert restored.hp == original.hp
    assert restored.max_hp == original.max_hp
    assert restored.keys == original.keys
    assert restored.gold == original.gold


def test_hp_clamped_when_corrupted():
    """Bug-fix v1.0: hp > max_hp num save corrompido deve ser cortado."""
    data = serialize_character(
        Character(name="X", race=Race.HUMANO, char_class=CharClass.GUERREIRO)
    )
    assert data is not None
    data["hp"] = 9999
    restored = deserialize_character(data)
    assert restored is not None
    assert restored.hp == restored.max_hp


def test_migrate_strips_sensitive_keys():
    """Bug-fix v1.0: gemini_api_key NUNCA carregada de save."""
    payload = {"gemini_api_key": "super-secret-leaked-key", "foo": "bar"}
    migrated = migrate(payload)
    assert "gemini_api_key" not in migrated
    assert migrated["foo"] == "bar"
    assert migrated["schema_version"] == SCHEMA_VERSION


def test_migrate_upgrades_gemini_model():
    payload = {"gemini_model": "gemini-2.0-flash"}
    migrated = migrate(payload)
    assert migrated["gemini_model"] == "gemini-2.5-flash-lite"


def test_write_save_strips_sensitive(tmp_path: Path):
    target = tmp_path / "s.json"
    write_save(target, {"foo": "bar", "gemini_api_key": "AAA"})
    raw = json.loads(target.read_text(encoding="utf-8"))
    assert "gemini_api_key" not in raw
    assert raw["foo"] == "bar"
    assert raw["schema_version"] == SCHEMA_VERSION


def test_read_save_migrates(tmp_path: Path):
    target = tmp_path / "old.json"
    target.write_text(
        json.dumps({"gemini_api_key": "X", "gemini_model": "gemini-2.0-flash"}),
        encoding="utf-8",
    )
    loaded = read_save(target)
    assert "gemini_api_key" not in loaded
    assert loaded["gemini_model"] == "gemini-2.5-flash-lite"
