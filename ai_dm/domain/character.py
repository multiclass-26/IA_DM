"""Personagem do jogador: classes, raças, atributos e estado.

Correções nesta v1.0:
- gain_xp() agora sobe múltiplos níveis numa só chamada (loop).
- take_damage / heal sempre fazem clamp em [0, max_hp].
- short_rest restaura HP e usos especiais.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from ai_dm.domain.dice import RNG, roll

ABILITY_NAMES = ["FOR", "DES", "CON", "INT", "SAB", "CAR"]
ABILITY_FULL = {
    "FOR": "Forca",
    "DES": "Destreza",
    "CON": "Constituicao",
    "INT": "Inteligencia",
    "SAB": "Sabedoria",
    "CAR": "Carisma",
}


class CharClass(Enum):
    GUERREIRO = "Guerreiro"
    MAGO = "Mago"
    LADINO = "Ladino"
    CLERIGO = "Clerigo"
    PALADINO = "Paladino"
    BRUXO = "Bruxo"


class Race(Enum):
    HUMANO = "Humano"
    ELFO = "Elfo"
    ANAO = "Anao"
    HALFLING = "Halfling"
    MEIO_ORC = "Meio-Orc"
    TIEFLING = "Tiefling"


CLASS_DATA = {
    CharClass.GUERREIRO: {
        "hit_die": "1d10",
        "hp_base": 10,
        "primary": "FOR",
        "equipment": ["Espada Longa", "Escudo", "Cota de Malha", "Pocao de Cura x2"],
        "description": "Mestre de armas e armaduras pesadas. A linha de frente do combate.",
        "special": "**Acao Impetuosa**: Ataca duas vezes no mesmo turno. 2 usos por descanso.",
        "damage": "1d8",
    },
    CharClass.MAGO: {
        "hit_die": "1d6",
        "hp_base": 6,
        "primary": "INT",
        "equipment": ["Cajado Arcano", "Grimorio", "Tunica", "Pocao de Cura x1"],
        "description": "Estudioso das artes arcanas. Magias devastadoras a distancia.",
        "special": "**Misseis Magicos**: 3 projeteis que acertam automaticamente (1d4+1 cada). 3 usos por descanso.",
        "damage": "1d6",
    },
    CharClass.LADINO: {
        "hit_die": "1d8",
        "hp_base": 8,
        "primary": "DES",
        "equipment": [
            "Adaga x2",
            "Arco Curto",
            "Armadura de Couro",
            "Kit de Ferramentas",
            "Pocao de Cura x1",
        ],
        "description": "Furtivo e letal. Especialista em armadilhas e ataques surpresa.",
        "special": "**Ataque Furtivo**: +2d6 de dano extra no ataque. 3 usos por descanso.",
        "damage": "1d4",
    },
    CharClass.CLERIGO: {
        "hit_die": "1d8",
        "hp_base": 8,
        "primary": "SAB",
        "equipment": ["Maca", "Escudo", "Cota de Escamas", "Simbolo Sagrado", "Pocao de Cura x2"],
        "description": "Canal divino. Cura ferimentos e repele mortos-vivos.",
        # NOTA DE DESIGN (v1.0): "Curar Ferimentos" cura E ataca normalmente no
        # mesmo turno, gastando apenas o uso especial. Decisão de design para
        # compensar o dano baixo do clérigo. Testado em test_combat.py.
        "special": (
            "**Curar Ferimentos**: Cura 1d8+SAB de HP. Pode atacar no mesmo turno. "
            "2 usos por descanso."
        ),
        "damage": "1d6",
    },
    CharClass.PALADINO: {
        "hit_die": "1d10",
        "hp_base": 10,
        "primary": "FOR",
        "equipment": ["Espada Longa", "Escudo", "Cota de Malha", "Simbolo Sagrado", "Pocao de Cura x1"],
        "description": "Cavaleiro sagrado. Combina combate marcial com poderes divinos.",
        "special": "**Golpe Divino**: +2d8 de dano radiante no ataque. 2 usos por descanso.",
        "damage": "1d8",
    },
    CharClass.BRUXO: {
        "hit_die": "1d8",
        "hp_base": 8,
        "primary": "CAR",
        "equipment": ["Foco Arcano", "Adaga Ritual", "Armadura de Couro", "Pocao de Cura x1"],
        "description": "Fez um pacto com uma entidade. Poder sombrio e raio eldritch.",
        "special": "**Raio Eldritch**: Ataque a distancia que acerta automaticamente por 1d10+CAR. 3 usos por descanso.",
        "damage": "1d8",
    },
}

RACE_DATA = {
    Race.HUMANO: {
        "bonuses": {"FOR": 1, "DES": 1, "CON": 1, "INT": 1, "SAB": 1, "CAR": 1},
        "trait": "*Versatil* -- +1 em todos os atributos.",
        "speed": 30,
    },
    Race.ELFO: {
        "bonuses": {"DES": 2, "INT": 1},
        "trait": "*Visao no Escuro* -- Enxerga no escuro. Resistencia a encantamentos.",
        "speed": 30,
    },
    Race.ANAO: {
        "bonuses": {"CON": 2, "SAB": 1},
        "trait": "*Resistencia Ana* -- Vantagem contra veneno. +2 HP por nivel.",
        "speed": 25,
    },
    Race.HALFLING: {
        "bonuses": {"DES": 2, "CAR": 1},
        "trait": "*Sortudo* -- Re-rola resultados 1 no d20.",
        "speed": 25,
    },
    Race.MEIO_ORC: {
        "bonuses": {"FOR": 2, "CON": 1},
        "trait": "*Resistencia Implacavel* -- Ao cair a 0 HP, volta com 1 HP (1x por descanso).",
        "speed": 30,
    },
    Race.TIEFLING: {
        "bonuses": {"CAR": 2, "INT": 1},
        "trait": "*Legado Infernal* -- Resistencia a fogo. Pode usar *Repreensao Infernal*.",
        "speed": 30,
    },
}

# Tabela de XP necessária acumulada por nível (D&D 5e simplificado).
XP_THRESHOLDS: dict[int, int] = {2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000}
MAX_LEVEL = 5


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


@dataclass
class Character:
    name: str
    race: Race
    char_class: CharClass
    level: int = 1
    abilities: dict = field(default_factory=dict)
    hp: int = 0
    max_hp: int = 0
    ac: int = 10
    inventory: list = field(default_factory=list)
    gold: int = 50
    xp: int = 0
    special_uses: int = 0
    max_special_uses: int = 0
    conditions: list = field(default_factory=list)
    keys: list = field(default_factory=list)

    # RNG opcional para gerar atributos. Setado via classmethod.
    _rng: random.Random | None = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if not self.abilities:
            self.abilities = self._generate_abilities()
        if self.max_hp == 0:
            self._calculate_hp(initial=True)
        self._calculate_ac()
        if not self.inventory:
            self.inventory = list(CLASS_DATA[self.char_class]["equipment"])
        if self.max_special_uses == 0:
            self.max_special_uses = (
                2 if self.char_class in [CharClass.GUERREIRO, CharClass.CLERIGO, CharClass.PALADINO] else 3
            )
            self.special_uses = self.max_special_uses

    def _generate_abilities(self) -> dict:
        rng = self._rng or RNG
        abilities = {}
        for ab in ABILITY_NAMES:
            rolls_result = sorted([rng.randint(1, 6) for _ in range(4)], reverse=True)
            abilities[ab] = sum(rolls_result[:3])
        primary = CLASS_DATA[self.char_class]["primary"]
        vals = list(abilities.values())
        best_val = max(vals)
        keys_list = list(abilities.keys())
        best_key = keys_list[vals.index(best_val)]
        if best_key != primary:
            abilities[best_key], abilities[primary] = abilities[primary], abilities[best_key]
        for ab, bonus in RACE_DATA[self.race]["bonuses"].items():
            abilities[ab] = abilities.get(ab, 10) + bonus
        return abilities

    def _calculate_hp(self, initial: bool = False) -> None:
        con_mod = ability_modifier(self.abilities.get("CON", 10))
        base = CLASS_DATA[self.char_class]["hp_base"]
        bonus = 2 if self.race == Race.ANAO else 0
        self.max_hp = base + con_mod + bonus + (self.level - 1) * (base // 2 + 1 + con_mod + bonus)
        if initial:
            self.hp = self.max_hp
        else:
            # Em level-up, garantir hp não fica acima do novo max.
            self.hp = min(self.hp, self.max_hp)

    def _calculate_ac(self) -> None:
        dex_mod = ability_modifier(self.abilities.get("DES", 10))
        if self.char_class in [CharClass.GUERREIRO, CharClass.PALADINO]:
            self.ac = 16 + min(dex_mod, 2)
        elif self.char_class == CharClass.CLERIGO:
            self.ac = 14 + min(dex_mod, 2) + 2
        elif self.char_class in [CharClass.LADINO, CharClass.BRUXO]:
            self.ac = 11 + dex_mod
        else:
            self.ac = 10 + dex_mod

    # -- API pública -------------------------------------------------------

    def mod(self, ability: str) -> int:
        return ability_modifier(self.abilities.get(ability, 10))

    def attack_mod(self) -> int:
        primary = CLASS_DATA[self.char_class]["primary"]
        return self.mod(primary) + 2

    def damage_dice(self) -> str:
        return CLASS_DATA[self.char_class]["damage"]

    def take_damage(self, amount: int) -> str:
        amount = max(0, int(amount))
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            return f"**{self.name}** caiu a 0 HP!"
        return f"**{self.name}** sofreu {amount} de dano! HP: {self.hp}/{self.max_hp}"

    def heal(self, amount: int) -> str:
        amount = max(0, int(amount))
        old_hp = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        healed = self.hp - old_hp
        return f"**{self.name}** recuperou {healed} HP! HP: {self.hp}/{self.max_hp}"

    def is_alive(self) -> bool:
        return self.hp > 0

    def short_rest(self) -> str:
        healed = roll(CLASS_DATA[self.char_class]["hit_die"])
        self.heal(healed.total)
        self.special_uses = self.max_special_uses
        return (
            f"Descanso curto! Recuperou {healed.total} HP. "
            f"Habilidades restauradas. HP: {self.hp}/{self.max_hp}"
        )

    def gain_xp(self, amount: int) -> str:
        """Adiciona XP e sobe TODOS os níveis acumulados que o XP permite."""
        if amount <= 0:
            return f"+0 XP. (Total: {self.xp} XP)"
        self.xp += int(amount)
        msg = f"+{amount} XP! (Total: {self.xp} XP)"

        levels_gained = 0
        while True:
            next_level = self.level + 1
            if next_level > MAX_LEVEL:
                break
            threshold = XP_THRESHOLDS.get(next_level)
            if threshold is None or self.xp < threshold:
                break
            self.level = next_level
            old_max = self.max_hp
            self._calculate_hp()
            # Curar pelo ganho de HP máximo (level-up totalmente curativo seria
            # OP; aqui só compensa o aumento).
            self.hp = min(self.max_hp, self.hp + (self.max_hp - old_max))
            levels_gained += 1

        if levels_gained:
            msg += f"\n**LEVEL UP!** Agora e nivel {self.level}! HP maximo: {self.max_hp}"
            if levels_gained > 1:
                msg += f" (+{levels_gained} niveis numa so vez)"
        return msg

    def has_key(self, key_name: str) -> bool:
        return key_name in self.keys

    def add_key(self, key_name: str) -> None:
        if key_name not in self.keys:
            self.keys.append(key_name)

    def character_sheet(self) -> str:
        cls_data = CLASS_DATA[self.char_class]
        lines = [
            f"## {self.name}",
            f"**{self.race.value} {self.char_class.value}** -- Nivel {self.level}",
            f"HP: **{self.hp}/{self.max_hp}** | CA: **{self.ac}** | Ouro: **{self.gold}**",
            f"XP: {self.xp}",
            "",
            "### Atributos",
        ]
        for ab in ABILITY_NAMES:
            val = self.abilities[ab]
            m = ability_modifier(val)
            mod_str = f"+{m}" if m >= 0 else str(m)
            lines.append(f"- **{ABILITY_FULL[ab]}**: {val} ({mod_str})")

        lines.append("\n### Habilidade Especial")
        lines.append(f"{cls_data['special']}")
        lines.append(f"Usos restantes: **{self.special_uses}/{self.max_special_uses}**")

        lines.append("\n### Raca")
        lines.append(RACE_DATA[self.race]["trait"])

        lines.append("\n### Inventario")
        for item in self.inventory:
            lines.append(f"- {item}")

        if self.keys:
            lines.append("\n### Chaves")
            for k in self.keys:
                lines.append(f"- {k}")

        return "\n".join(lines)
