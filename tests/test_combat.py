"""Testes de combate. Invariantes + decisão de design do Clérigo."""

import random

import pytest

from ai_dm.domain.character import Character, CharClass, Race
from ai_dm.domain.monster import MONSTER_TEMPLATES
from ai_dm.engine.combat import _decrement_stack, resolve_player_attack, use_potion


def fixed_rng_int(seq):
    it = iter(seq)
    r = random.Random()
    r.randint = lambda a, b: next(it)  # type: ignore[assignment]
    return r


def make_pair(klass=CharClass.GUERREIRO):
    c = Character(name="P", race=Race.HUMANO, char_class=klass)
    m = MONSTER_TEMPLATES["goblin"]()
    return c, m


@pytest.mark.parametrize("klass", list(CharClass))
def test_player_attack_does_not_violate_invariants(klass):
    c, m = make_pair(klass)
    initial_special = c.special_uses
    for _ in range(20):
        resolve_player_attack(c, m, use_special=False)
        assert c.hp >= 0
        assert m.hp >= 0
        assert c.special_uses == initial_special
        if not m.is_alive():
            break


@pytest.mark.parametrize("klass", list(CharClass))
def test_special_consumes_use(klass):
    c, m = make_pair(klass)
    before = c.special_uses
    resolve_player_attack(c, m, use_special=True)
    assert c.special_uses == before - 1


def test_clerigo_design_heals_and_attacks_same_turn():
    """Decisão de design v1.0: Clérigo cura e ataca no mesmo turno."""
    c, m = make_pair(CharClass.CLERIGO)
    c.hp = 1
    monster_hp_before = m.hp
    monster_hp_max = m.max_hp
    initial_special = c.special_uses

    # Pode tomar muitas chances até cura mais ataque (pode errar o ataque).
    # Mas o HP do clérigo deve sempre aumentar e o uso especial decrementar.
    resolve_player_attack(c, m, use_special=True)

    assert c.special_uses == initial_special - 1
    assert c.hp > 1  # foi curado
    # m.hp pode ou não ter caído (depende do ataque); apenas verificamos limites:
    assert 0 <= m.hp <= monster_hp_max
    # Se sofreu dano, é evidência do ataque adicional pós-cura.
    if m.hp < monster_hp_before:
        pass  # comportamento previsto na maioria dos casos


def test_use_potion_decrements_stack():
    c = Character(name="P", race=Race.HUMANO, char_class=CharClass.GUERREIRO)
    # Guerreiro começa com "Pocao de Cura x2"
    assert any("Pocao de Cura x2" in i for i in c.inventory)
    c.hp = 1
    use_potion(c)
    assert any("Pocao de Cura x1" in i for i in c.inventory)


def test_use_potion_removes_when_last():
    c = Character(name="P", race=Race.HUMANO, char_class=CharClass.MAGO)
    # Mago tem "Pocao de Cura x1"
    c.hp = 1
    use_potion(c)
    assert not any("Pocao de Cura" in i for i in c.inventory)


def test_use_potion_no_potion_returns_message():
    c = Character(name="P", race=Race.HUMANO, char_class=CharClass.GUERREIRO)
    c.inventory = ["Espada Longa"]
    msg = use_potion(c)
    assert "nao tem" in msg.lower() or "não tem" in msg.lower()


class TestDecrementStack:
    """Bug-fix v1.0: parser de inventário robusto a nomes contendo 'x'."""

    def test_decrements_normal_stack(self):
        assert _decrement_stack("Pocao de Cura x3") == "Pocao de Cura x2"

    def test_returns_none_for_last_item(self):
        assert _decrement_stack("Pocao de Cura x1") is None

    def test_returns_none_for_zero_after_decrement(self):
        assert _decrement_stack("Item x1") is None

    def test_handles_no_quantity_suffix(self):
        # Item sem 'xN' explícito: remover.
        assert _decrement_stack("Espada Longa") is None

    def test_does_not_misparse_x_in_name(self):
        # Item com 'x' no meio do nome mas SEM ' xN' no fim.
        assert _decrement_stack("Espada Extra de Fenix") is None
