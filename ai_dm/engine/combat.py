"""Resolução de combate. Sem efeitos colaterais de UI."""

from __future__ import annotations

import re

from ai_dm.domain.character import CLASS_DATA, Character, CharClass
from ai_dm.domain.dice import roll, roll_check
from ai_dm.domain.monster import Monster


def _single_attack(character: Character, monster: Monster) -> str:
    lines: list[str] = []
    atk = roll_check(character.attack_mod(), monster.ac)
    lines.append(atk.description)
    if atk.success:
        dmg = roll(character.damage_dice())
        total = dmg.total + character.mod(CLASS_DATA[character.char_class]["primary"])
        if atk.critical:
            total *= 2
            lines.append(f"Dano CRITICO: **{total}**!")
        else:
            lines.append(f"Dano: **{total}**")
        lines.append(monster.take_damage(total))
    return "\n".join(lines)


def resolve_player_attack(
    character: Character, monster: Monster, use_special: bool = False
) -> str:
    """Resolve uma ação de ataque do jogador.

    Decisão de design (v1.0):
      - **Clérigo** com `use_special=True` CURA e em seguida ATACA no mesmo
        turno (decisão consciente para compensar dano baixo). Demais classes
        com `use_special=True` substituem o ataque normal por sua habilidade.
    """
    lines: list[str] = []

    if use_special and character.special_uses > 0:
        character.special_uses -= 1

        if character.char_class == CharClass.MAGO:
            total_dmg = 0
            missile_desc = []
            for _ in range(3):
                d = roll("1d4+1")
                total_dmg += d.total
                missile_desc.append(str(d.total))
            lines.append(f"**Misseis Magicos!** -> {', '.join(missile_desc)} = **{total_dmg}** de dano!")
            lines.append(monster.take_damage(total_dmg))
            return "\n".join(lines)

        if character.char_class == CharClass.CLERIGO:
            heal_roll = roll("1d8")
            heal_total = heal_roll.total + character.mod("SAB")
            lines.append("**Curar Ferimentos!**")
            lines.append(character.heal(heal_total))
            lines.append("*(Ainda pode atacar normalmente)*")
            # Fall through -> ataque normal abaixo. Comportamento intencional.

        elif character.char_class == CharClass.GUERREIRO:
            lines.append("**Acao Impetuosa!** Dois ataques!")
            for _ in range(2):
                lines.append(_single_attack(character, monster))
                if not monster.is_alive():
                    break
            return "\n".join(lines)

        elif character.char_class == CharClass.LADINO:
            lines.append("**Ataque Furtivo!**")
            atk = roll_check(character.attack_mod(), monster.ac)
            lines.append(atk.description)
            if atk.success:
                dmg = roll(character.damage_dice())
                sneak = roll("2d6")
                total = dmg.total + sneak.total + character.mod(CLASS_DATA[character.char_class]["primary"])
                if atk.critical:
                    total *= 2
                lines.append(f"Dano: {dmg.total} + {sneak.total} furtivo = **{total}**")
                lines.append(monster.take_damage(total))
            return "\n".join(lines)

        elif character.char_class == CharClass.PALADINO:
            lines.append("**Golpe Divino!**")
            atk = roll_check(character.attack_mod(), monster.ac)
            lines.append(atk.description)
            if atk.success:
                dmg = roll(character.damage_dice())
                smite = roll("2d8")
                total = dmg.total + smite.total + character.mod("FOR")
                if atk.critical:
                    total *= 2
                lines.append(f"Dano: {dmg.total} + {smite.total} radiante = **{total}**")
                lines.append(monster.take_damage(total))
            return "\n".join(lines)

        elif character.char_class == CharClass.BRUXO:
            lines.append("**Raio Eldritch!**")
            dmg = roll("1d10")
            total = dmg.total + character.mod("CAR")
            lines.append(f"Acerto automatico! Dano: {dmg.total}+{character.mod('CAR')} = **{total}**")
            lines.append(monster.take_damage(total))
            return "\n".join(lines)

    lines.append(_single_attack(character, monster))
    return "\n".join(lines)


def resolve_monster_attack(monster: Monster, character: Character) -> str:
    lines = [f"\n**{monster.name}** ataca **{character.name}**!"]
    atk = roll_check(monster.attack_bonus, character.ac)
    lines.append(atk.description)
    if atk.success:
        dmg = roll(monster.damage)
        total = dmg.total
        if atk.critical:
            total *= 2
            lines.append(f"Dano CRITICO: **{total}**!")
        else:
            lines.append(f"Dano: **{total}**")
        lines.append(character.take_damage(total))
    else:
        lines.append("O ataque erra!")
    return "\n".join(lines)


# Regex para itens em estoque: "Nome xN" -> grupo "name" e "qty".
_STACK_RE = re.compile(r"^(?P<name>.+?)\s*x\s*(?P<qty>\d+)\s*$")


def _decrement_stack(item: str) -> str | None:
    """Decrementa um item em estoque ('Pocao x3' -> 'Pocao x2').

    Retorna None quando o item deve ser removido. Robusto a nomes com 'x'
    no meio (ex. 'Espada Magica Extra').
    """
    m = _STACK_RE.match(item)
    if not m:
        return None  # item simples -> remover
    qty = int(m.group("qty")) - 1
    if qty <= 0:
        return None
    return f"{m.group('name').strip()} x{qty}"


def use_potion(character: Character) -> str:
    potions = [i for i, item in enumerate(character.inventory) if "Pocao de Cura" in item]
    if not potions:
        return "Voce nao tem pocoes de cura!"

    idx = potions[0]
    item = character.inventory[idx]
    new_value = _decrement_stack(item)
    if new_value is None:
        character.inventory.pop(idx)
    else:
        character.inventory[idx] = new_value

    heal_roll = roll("2d4+2")
    result = character.heal(heal_roll.total)
    return f"Bebeu uma Pocao de Cura! {heal_roll.description}\n{result}"
