"""Dados e checks. Parser robusto para notação NdX±M."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

RNG = random.SystemRandom()

# Aceita: "1d20", "2d6+3", "3d8-1", "d20" (1d20 implícito), com espaços.
_DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class DiceRoll:
    """Resultado estruturado de uma rolagem."""

    rolls: list[int]
    modifier: int
    total: int
    description: str

    # Compat: permite acesso por chave como dict (código legado usava dict).
    def __getitem__(self, key: str):  # pragma: no cover - thin shim
        return getattr(self, key)

    def get(self, key: str, default=None):  # pragma: no cover
        return getattr(self, key, default)


def _format_modifier(modifier: int) -> str:
    if modifier > 0:
        return f"+{modifier}"
    if modifier < 0:
        return str(modifier)
    return ""


def roll(notation: str, rng: random.Random | None = None) -> DiceRoll:
    """Rola dados no formato NdX[+/-M]. Lança ValueError em entrada inválida."""
    if not isinstance(notation, str):
        raise ValueError(f"Notação inválida: {notation!r}")

    match = _DICE_RE.match(notation.replace(" ", ""))
    if not match:
        raise ValueError(f"Notação de dado inválida: {notation!r}")

    num_str, sides_str, mod_str = match.groups()
    num = int(num_str) if num_str else 1
    sides = int(sides_str)
    modifier = int(mod_str.replace(" ", "")) if mod_str else 0

    if num <= 0 or num > 100:
        raise ValueError(f"Número de dados fora de [1,100]: {num}")
    if sides < 2 or sides > 1000:
        raise ValueError(f"Lados de dado fora de [2,1000]: {sides}")

    r = rng or RNG
    rolls = [r.randint(1, sides) for _ in range(num)]
    total = max(sum(rolls) + modifier, 0)

    mod_repr = _format_modifier(modifier)
    desc = (
        f"[dado] {num}d{sides}{mod_repr} = "
        f"[{', '.join(str(v) for v in rolls)}]{mod_repr} = **{total}**"
    )
    return DiceRoll(rolls=rolls, modifier=modifier, total=total, description=desc)


@dataclass(frozen=True)
class CheckResult:
    natural: int
    total: int
    dc: int
    success: bool
    critical: bool
    fumble: bool
    description: str

    def __getitem__(self, key: str):  # pragma: no cover
        return getattr(self, key)

    def get(self, key: str, default=None):  # pragma: no cover
        return getattr(self, key, default)


def roll_check(modifier: int = 0, dc: int = 10, rng: random.Random | None = None) -> CheckResult:
    """Rola 1d20 + modificador contra uma DC."""
    r = roll("1d20", rng=rng)
    natural = r.rolls[0]
    total = natural + modifier
    critical = natural == 20
    fumble = natural == 1
    success = (total >= dc and not fumble) or critical

    if critical:
        label = "SUCESSO CRITICO!"
    elif fumble:
        label = "FALHA CRITICA!"
    elif success:
        label = "Sucesso"
    else:
        label = "Falha"

    mod_repr = _format_modifier(modifier) or "+0"
    desc = f"d20({natural}){mod_repr} = **{total}** vs DC {dc} -- {label}"
    return CheckResult(
        natural=natural,
        total=total,
        dc=dc,
        success=success,
        critical=critical,
        fumble=fumble,
        description=desc,
    )
