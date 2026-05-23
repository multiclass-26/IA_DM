"""Testes de dados (NdX±M)."""

import random

import pytest

from ai_dm.domain.dice import roll, roll_check


def fixed_rng(seq):
    """RNG determinístico que devolve valores de uma fila."""
    it = iter(seq)
    r = random.Random()
    r.randint = lambda a, b: next(it)  # type: ignore[assignment]
    return r


class TestRoll:
    def test_basic_d20(self):
        rng = fixed_rng([17])
        result = roll("1d20", rng=rng)
        assert result.total == 17
        assert result.rolls == [17]
        assert result.modifier == 0

    def test_with_positive_modifier(self):
        rng = fixed_rng([4, 5])
        result = roll("2d6+3", rng=rng)
        assert result.total == 12
        assert result.modifier == 3
        assert result.rolls == [4, 5]

    def test_with_negative_modifier(self):
        rng = fixed_rng([6, 6, 6])
        result = roll("3d8-1", rng=rng)
        assert result.total == 17
        assert result.modifier == -1

    def test_d20_with_minus_one(self):
        rng = fixed_rng([10])
        result = roll("1d20-1", rng=rng)
        assert result.total == 9
        assert result.modifier == -1

    def test_implicit_one_die(self):
        rng = fixed_rng([4])
        result = roll("d6", rng=rng)
        assert result.total == 4
        assert result.rolls == [4]

    def test_total_never_negative(self):
        rng = fixed_rng([1, 1])
        result = roll("2d6-50", rng=rng)
        assert result.total == 0

    @pytest.mark.parametrize("bad", ["", "abc", "1d", "d", "20", "1d0", "-1d6", "1dX", "1d6+", "1d6+abc"])
    def test_invalid_notation_raises(self, bad):
        with pytest.raises(ValueError):
            roll(bad)

    def test_spaces_are_ignored(self):
        rng = fixed_rng([3])
        assert roll("1d6 + 2", rng=rng).total == 5


class TestRollCheck:
    def test_critical_success(self):
        rng = fixed_rng([20])
        r = roll_check(0, dc=30, rng=rng)
        assert r.critical is True
        assert r.success is True

    def test_critical_fumble(self):
        rng = fixed_rng([1])
        r = roll_check(50, dc=5, rng=rng)
        assert r.fumble is True
        assert r.success is False

    def test_normal_success(self):
        rng = fixed_rng([15])
        r = roll_check(2, dc=15, rng=rng)
        assert r.success is True
        assert r.total == 17

    def test_normal_failure(self):
        rng = fixed_rng([5])
        r = roll_check(0, dc=15, rng=rng)
        assert r.success is False
