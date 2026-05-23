"""Monstros e tabela de encontros."""

from __future__ import annotations

import random
from dataclasses import dataclass

from ai_dm.domain.dice import RNG


@dataclass
class Monster:
    name: str
    hp: int
    max_hp: int
    ac: int
    attack_bonus: int
    damage: str
    xp_reward: int
    description: str = ""
    special: str = ""

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> str:
        amount = max(0, int(amount))
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            return f"**{self.name}** foi derrotado!"
        return f"**{self.name}** sofreu {amount} de dano! HP: {self.hp}/{self.max_hp}"


MONSTER_TEMPLATES = {
    "goblin": lambda: Monster(
        "Goblin", 7, 7, 13, 4, "1d6+2", 50,
        "Goblin astuto com cimitarra enferrujada.",
        "Fuga: esconde-se como acao bonus.",
    ),
    "esqueleto": lambda: Monster(
        "Esqueleto", 13, 13, 13, 4, "1d6+2", 50,
        "Ossos animados por magia negra.",
        "Vulneravel a dano contundente.",
    ),
    "kobold": lambda: Monster(
        "Kobold", 5, 5, 12, 4, "1d4+2", 25,
        "Reptil covarde que ataca em bando.",
        "Tatica de Bando: vantagem com aliado adjacente.",
    ),
    "orc": lambda: Monster(
        "Orc", 15, 15, 13, 5, "1d12+3", 100,
        "Orc musculoso com machado de guerra.",
        "Agressivo: avanca como acao bonus.",
    ),
    "aranha_gigante": lambda: Monster(
        "Aranha Gigante", 26, 26, 14, 5, "1d8+3", 200,
        "Aranha venenosa do tamanho de um cavalo.",
        "Veneno: save CON DC 11 ou +2d8 veneno.",
    ),
    "mimic": lambda: Monster(
        "Mimico", 58, 58, 12, 5, "1d8+3", 450,
        "O que parecia um bau revelou dentes afiados!",
        "Aderente: FOR DC 13 para se soltar.",
    ),
    "zumbi": lambda: Monster(
        "Zumbi", 22, 22, 8, 3, "1d6+1", 50,
        "Carne putrefata, avanco implacavel.",
        "Resistencia Morta-Viva: save CON DC 5+dano ao cair a 0.",
    ),
    "lobo_terrivel": lambda: Monster(
        "Lobo Terrivel", 37, 37, 14, 5, "2d6+3", 200,
        "Lobo enorme com olhos vermelhos.",
        "Derrubar: FOR DC 13 ou cai no chao.",
    ),
    "cultista": lambda: Monster(
        "Cultista Fanatico", 22, 22, 13, 4, "1d8+2", 100,
        "Encapuzado murmurando oracoes sombrias.",
        "Escudo de Fe: +2 CA uma vez por combate.",
    ),
    "esqueleto_guerreiro": lambda: Monster(
        "Esqueleto Guerreiro", 30, 30, 15, 6, "1d10+3", 150,
        "Esqueleto com armadura completa e espada.",
        "Ataque duplo: ataca 2x por turno.",
    ),
    "troll": lambda: Monster(
        "Troll", 84, 84, 15, 7, "2d6+4", 1800,
        "Criatura enorme com regeneracao sobrenatural.",
        "Regeneracao: +10 HP/turno (exceto fogo/acido).",
    ),
    "dragao_jovem": lambda: Monster(
        "Dragao Jovem", 110, 110, 18, 10, "2d10+5", 5000,
        "Dragao imponente de escamas reluzentes.",
        "Sopro: 10d6 dano, save DES DC 15 para metade.",
    ),
}


def get_encounter_for_level(level: int, rng: random.Random | None = None) -> list[Monster]:
    r = rng or RNG
    if level <= 1:
        options = [
            [MONSTER_TEMPLATES["goblin"](), MONSTER_TEMPLATES["goblin"]()],
            [MONSTER_TEMPLATES["kobold"](), MONSTER_TEMPLATES["kobold"](), MONSTER_TEMPLATES["kobold"]()],
            [MONSTER_TEMPLATES["esqueleto"]()],
            [MONSTER_TEMPLATES["zumbi"]()],
        ]
    elif level <= 2:
        options = [
            [MONSTER_TEMPLATES["orc"]()],
            [MONSTER_TEMPLATES["esqueleto"](), MONSTER_TEMPLATES["esqueleto"]()],
            [MONSTER_TEMPLATES["cultista"](), MONSTER_TEMPLATES["cultista"]()],
            [MONSTER_TEMPLATES["lobo_terrivel"]()],
        ]
    elif level <= 3:
        options = [
            [MONSTER_TEMPLATES["aranha_gigante"]()],
            [MONSTER_TEMPLATES["orc"](), MONSTER_TEMPLATES["orc"]()],
            [MONSTER_TEMPLATES["mimic"]()],
            [MONSTER_TEMPLATES["esqueleto_guerreiro"](), MONSTER_TEMPLATES["goblin"]()],
        ]
    else:
        options = [
            [MONSTER_TEMPLATES["troll"]()],
            [MONSTER_TEMPLATES["aranha_gigante"](), MONSTER_TEMPLATES["aranha_gigante"]()],
            [MONSTER_TEMPLATES["mimic"](), MONSTER_TEMPLATES["orc"]()],
        ]
    return r.choice(options)
