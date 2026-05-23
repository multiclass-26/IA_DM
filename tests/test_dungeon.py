"""Testes do gerador de dungeon. Bug-fix v1.0: nunca chave órfã."""

import random

import pytest

from ai_dm.domain.dungeon import generate_dungeon_map
from ai_dm.llm.prompts import get_room_sequence


@pytest.mark.parametrize("total_rooms", [5, 7, 10])
@pytest.mark.parametrize("seed", list(range(20)))
def test_no_orphan_keys(total_rooms, seed):
    """Para todo bloqueio, deve existir chave; e vice-versa."""
    rng = random.Random(seed)
    sequence = get_room_sequence(total_rooms)
    dungeon = generate_dungeon_map(sequence, num_locks=2, rng=rng)

    locked_keys = {lock["key_name"] for lock in dungeon.locks}
    key_rooms = {room.has_key for room in dungeon.rooms if room.has_key}
    # Toda chave atribuída a uma sala precisa existir num bloqueio.
    assert key_rooms <= locked_keys, f"chaves orfas: {key_rooms - locked_keys}"
    # Todo bloqueio precisa ter uma sala-fonte com a chave correspondente.
    for lock in dungeon.locks:
        sources = [r for r in dungeon.rooms if r.has_key == lock["key_name"]]
        assert len(sources) >= 1, f"bloqueio {lock['key_name']} sem chave"


def test_first_room_is_never_locked():
    dungeon = generate_dungeon_map(["exploration"] * 7, num_locks=2)
    assert not dungeon.rooms[0].locked


def test_zero_locks_means_no_keys():
    dungeon = generate_dungeon_map(["exploration"] * 7, num_locks=0)
    assert dungeon.locks == []
    assert all(not r.has_key for r in dungeon.rooms)


def test_room_sequence_canonical():
    assert get_room_sequence(5)[-1] == "boss"
    assert get_room_sequence(7)[-1] == "boss"
    assert get_room_sequence(10)[-1] == "boss"


@pytest.mark.parametrize("total_rooms", [5, 7, 10])
def test_room_count_matches_sequence(total_rooms):
    seq = get_room_sequence(total_rooms)
    dungeon = generate_dungeon_map(seq, num_locks=1)
    assert len(dungeon.rooms) == total_rooms
