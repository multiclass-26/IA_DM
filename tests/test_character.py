"""Testes do personagem: criação, nivel-up loop, dano/cura clamp."""

import pytest

from ai_dm.domain.character import (
    XP_THRESHOLDS,
    Character,
    CharClass,
    Race,
    ability_modifier,
)


def make_char(klass=CharClass.GUERREIRO, race=Race.HUMANO) -> Character:
    return Character(name="Teste", race=race, char_class=klass)


class TestCreation:
    @pytest.mark.parametrize("klass", list(CharClass))
    def test_each_class_has_valid_stats(self, klass):
        c = Character(name="X", race=Race.HUMANO, char_class=klass)
        assert c.hp == c.max_hp
        assert c.hp > 0
        # AC pode ser < 10 para classes sem armadura com DES baixa; é esperado.
        assert c.ac >= 5
        assert c.max_special_uses > 0
        assert len(c.inventory) > 0

    @pytest.mark.parametrize("race", list(Race))
    def test_each_race_applies_bonuses(self, race):
        c = Character(name="X", race=race, char_class=CharClass.GUERREIRO)
        # Pelo menos um atributo deve refletir bônus racial (>= 10).
        assert any(v >= 10 for v in c.abilities.values())


class TestAbilityModifier:
    @pytest.mark.parametrize("score,expected", [(1, -5), (10, 0), (11, 0), (12, 1), (15, 2), (20, 5)])
    def test_modifier(self, score, expected):
        assert ability_modifier(score) == expected


class TestTakeDamageHeal:
    def test_damage_clamped_at_zero(self):
        c = make_char()
        c.take_damage(99999)
        assert c.hp == 0
        assert not c.is_alive()

    def test_heal_clamped_at_max(self):
        c = make_char()
        c.hp = 1
        c.heal(99999)
        assert c.hp == c.max_hp

    def test_negative_damage_is_zero(self):
        c = make_char()
        original = c.hp
        c.take_damage(-5)
        assert c.hp == original


class TestGainXp:
    """Bug-fix v1.0: gain_xp deve subir múltiplos níveis num único ganho."""

    def test_single_level_up(self):
        c = make_char()
        msg = c.gain_xp(XP_THRESHOLDS[2])
        assert c.level == 2
        assert "LEVEL UP" in msg

    def test_multi_level_up_in_one_call(self):
        c = make_char()
        # XP suficiente para chegar a nível 4 de uma só vez.
        c.gain_xp(XP_THRESHOLDS[4])
        assert c.level == 4

    def test_xp_below_threshold_does_not_level(self):
        c = make_char()
        c.gain_xp(XP_THRESHOLDS[2] - 1)
        assert c.level == 1

    def test_does_not_exceed_max_level(self):
        c = make_char()
        c.gain_xp(10_000_000)
        assert c.level == 5  # MAX_LEVEL

    def test_negative_xp_noop(self):
        c = make_char()
        c.gain_xp(-100)
        assert c.xp == 0
        assert c.level == 1


class TestKeys:
    def test_add_and_has_key(self):
        c = make_char()
        c.add_key("Gema de Sangue")
        assert c.has_key("Gema de Sangue")

    def test_add_key_idempotent(self):
        c = make_char()
        c.add_key("X")
        c.add_key("X")
        assert c.keys == ["X"]
