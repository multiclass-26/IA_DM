"""Gerador procedural de dungeon (grafo de salas) + renderização SVG.

Correção v1.0: o bug onde um bloqueio era abandonado se não houvesse sala
de destino, mas a chave já tinha sido colocada (orfã), foi eliminado: a
chave só é atribuída APÓS o lock_room ser confirmado.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from ai_dm.domain.dice import RNG

log = logging.getLogger(__name__)


ROOM_NAMES = {
    "exploration": [
        "Antecamara das Sombras", "Salao dos Ecos", "Corredor Serpenteante",
        "Cripta dos Sussurros", "Galeria dos Espelhos", "Camara do Oraculo",
        "Passagem dos Ventos", "Sala dos Pilares", "Portico Arcano",
        "Ante-sala do Guardiao", "Corredor dos Ossos", "Salao Esquecido",
    ],
    "combat": [
        "Arena do Sangue", "Covil das Bestas", "Salao da Emboscada",
        "Fossa dos Condenados", "Clareira da Carnificina", "Tumulo Profanado",
        "Camara dos Horrores", "Ninho da Praga", "Campo de Batalha Eterno",
    ],
    "treasure": [
        "Cofre do Tirano", "Tesouro Esquecido", "Relicario Sagrado",
        "Sala do Butim", "Camara Dourada", "Alcova do Dragao",
    ],
    "rest": [
        "Refugio da Fonte", "Fogueira dos Viajantes", "Santuario Oculto",
        "Gruta da Serenidade", "Alcova Protegida", "Sala da Fonte Curativa",
    ],
    "boss": [
        "Trono do Flagelo", "Camara do Senhor Sombrio", "Sala do Julgamento Final",
        "Arena do Destruidor", "Sanctum do Terror", "Salao do Pesadelo",
    ],
}

LOCK_TEMPLATES = [
    {
        "key_name": "Cranio de Vardak",
        "key_description": "Um cranio humano com runas gravadas nos ossos",
        "lock_description": "Uma porta de pedra com uma cavidade no formato de um cranio",
        "key_location_type": "combat",
        "lock_location_type": "treasure",
    },
    {
        "key_name": "Gema de Sangue",
        "key_description": "Uma gema carmesim que pulsa com luz propria",
        "lock_description": "Um bau de obsidiana com um encaixe para uma gema vermelha",
        "key_location_type": "exploration",
        "lock_location_type": "treasure",
    },
    {
        "key_name": "Selo do Arconte",
        "key_description": "Um medalhao de prata com o simbolo de uma ordem antiga",
        "lock_description": "Uma passagem selada por magia com o simbolo de uma ordem gravado",
        "key_location_type": "combat",
        "lock_location_type": "exploration",
    },
    {
        "key_name": "Chave de Ferro Negro",
        "key_description": "Uma chave retorcida feita de ferro negro, gelada ao toque",
        "lock_description": "Uma porta de carvalho reforcada com uma fechadura ornamentada",
        "key_location_type": "exploration",
        "lock_location_type": "treasure",
    },
    {
        "key_name": "Fragmento do Obelisco",
        "key_description": "Um pedaco de pedra gravada com linguagem arcana",
        "lock_description": "Um obelisco partido com uma cavidade onde um fragmento se encaixa",
        "key_location_type": "combat",
        "lock_location_type": "boss",
    },
]


@dataclass
class DungeonRoom:
    number: int
    room_type: str
    name: str
    connections: list[int] = field(default_factory=list)
    explored: bool = False
    locked: bool = False
    lock_info: dict = field(default_factory=dict)
    has_key: str = ""


@dataclass
class DungeonMap:
    rooms: list[DungeonRoom] = field(default_factory=list)
    locks: list[dict] = field(default_factory=list)
    current_room: int = 1

    def get_room(self, number: int) -> DungeonRoom | None:
        for r in self.rooms:
            if r.number == number:
                return r
        return None


def generate_dungeon_map(
    room_sequence: list[str],
    num_locks: int = 1,
    rng: random.Random | None = None,
) -> DungeonMap:
    """Gera a dungeon. Bloqueios e chaves SEMPRE em par (ou nenhum)."""
    r = rng or RNG
    rooms: list[DungeonRoom] = []
    used_names: set[str] = set()

    for i, room_type in enumerate(room_sequence):
        room_num = i + 1
        pool = ROOM_NAMES.get(room_type, ROOM_NAMES["exploration"])
        available = [n for n in pool if n not in used_names] or pool
        name = r.choice(available)
        used_names.add(name)

        room = DungeonRoom(number=room_num, room_type=room_type, name=name)
        if room_num > 1:
            room.connections.append(room_num - 1)
            rooms[room_num - 2].connections.append(room_num)
        rooms.append(room)

    total = len(rooms)
    if total >= 7:
        branch_from = r.randint(2, total // 2)
        branch_to = r.randint(total // 2 + 1, total - 1)
        if branch_to not in rooms[branch_from - 1].connections:
            rooms[branch_from - 1].connections.append(branch_to)
            rooms[branch_to - 1].connections.append(branch_from)

    locks: list[dict] = []
    num_locks = max(0, min(num_locks, len(LOCK_TEMPLATES), total // 3))

    if num_locks > 0:
        chosen_templates = r.sample(LOCK_TEMPLATES, num_locks)
        for tmpl in chosen_templates:
            first_half = [
                room for room in rooms[1: max(2, total // 2)]
                if not room.has_key  # bug-fix v1.0: nunca sobrescreve chave existente
            ]
            second_half = [room for room in rooms[total // 2: total - 1] if not room.locked]

            lock_candidates = [room for room in second_half if room.room_type == tmpl["lock_location_type"]]
            if not lock_candidates:
                lock_candidates = second_half
            if not lock_candidates:
                log.warning("Bloqueio %s ignorado: nenhuma sala-destino disponivel.", tmpl["key_name"])
                continue

            key_candidates = [room for room in first_half if room.room_type == tmpl["key_location_type"]]
            if not key_candidates:
                key_candidates = first_half
            if not key_candidates:
                log.warning("Bloqueio %s ignorado: nenhuma sala-chave disponivel.", tmpl["key_name"])
                continue

            # Só comprometemos os estados após ambas serem confirmadas.
            lock_room = r.choice(lock_candidates)
            key_room = r.choice(key_candidates)

            key_room.has_key = tmpl["key_name"]
            lock_room.locked = True
            lock_room.lock_info = {
                "key_name": tmpl["key_name"],
                "description": tmpl["lock_description"],
            }
            locks.append({
                "key_name": tmpl["key_name"],
                "key_description": tmpl["key_description"],
                "key_room": key_room.number,
                "lock_description": tmpl["lock_description"],
                "lock_room": lock_room.number,
                "unlocked": False,
            })

    return DungeonMap(rooms=rooms, locks=locks, current_room=1)


def get_lock_status_text(dungeon: DungeonMap) -> str:
    active = [lock for lock in dungeon.locks if not lock["unlocked"]]
    if not active:
        return ""
    lines = ["**Bloqueios ativos:**"]
    for lock in active:
        lines.append(
            f"- Sala {lock['lock_room']}: {lock['lock_description']} (requer: *{lock['key_name']}*)"
        )
    return "\n".join(lines)


def render_map_svg(dungeon: DungeonMap) -> str:
    """Renderiza o mapa como SVG. Layout: serpentina até 10 salas, grade 5xN acima."""
    rooms = dungeon.rooms
    total = len(rooms)
    if total == 0:
        return "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 40'/>"

    cols = 5 if total > 10 else min(4, total)
    row_height = 100
    col_width = 200
    padding = 60
    node_w, node_h = 160, 50

    positions: dict[int, tuple[int, int]] = {}
    for i, room in enumerate(rooms):
        row = i // cols
        col = i % cols
        if row % 2 == 1:
            col = cols - 1 - col
        positions[room.number] = (padding + col * col_width, padding + row * row_height)

    max_x = max(p[0] for p in positions.values()) + node_w + padding
    max_y = max(p[1] for p in positions.values()) + node_h + padding

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {max_x} {max_y}" '
        f'style="width:100%;max-width:{max_x}px;background:#14141c;border-radius:12px;padding:8px;">'
    ]

    drawn_edges: set[tuple[int, int]] = set()
    for room in rooms:
        x1, y1 = positions[room.number]
        cx1, cy1 = x1 + node_w // 2, y1 + node_h // 2
        for conn in room.connections:
            edge = (min(room.number, conn), max(room.number, conn))
            if edge in drawn_edges:
                continue
            drawn_edges.add(edge)
            x2, y2 = positions[conn]
            cx2, cy2 = x2 + node_w // 2, y2 + node_h // 2
            locked_edge = any(
                not lock["unlocked"] and lock["lock_room"] in edge for lock in dungeon.locks
            )
            color = "#ef4444" if locked_edge else "#3f3f5c"
            dash = 'stroke-dasharray="6,4"' if locked_edge else ""
            parts.append(
                f'<line x1="{cx1}" y1="{cy1}" x2="{cx2}" y2="{cy2}" '
                f'stroke="{color}" stroke-width="2" {dash}/>'
            )

    icon_map = {"exploration": "?", "combat": "X", "treasure": "$", "rest": "+", "boss": "!!"}
    for room in rooms:
        x, y = positions[room.number]
        is_current = room.number == dungeon.current_room
        if is_current:
            fill, stroke, text_color = "#7c3aed", "#a78bfa", "#fff"
        elif room.explored:
            fill, stroke, text_color = "#1e1e2e", "#3f3f5c", "#9ca3af"
        elif room.locked:
            fill, stroke, text_color = "#1e1e2e", "#ef4444", "#ef4444"
        else:
            fill, stroke, text_color = "#1e1e2e", "#3f3f5c", "#6b7280"

        parts.append(
            f'<rect x="{x}" y="{y}" width="{node_w}" height="{node_h}" '
            f'rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
        icon = icon_map.get(room.room_type, "?")
        if room.locked and not any(lock["unlocked"] for lock in dungeon.locks if lock["lock_room"] == room.number):
            icon = "#"
        parts.append(
            f'<text x="{x + 8}" y="{y + 18}" font-family="monospace" font-size="11" '
            f'fill="{text_color}" font-weight="bold">{room.number}. {icon}</text>'
        )
        display_name = (room.name[:18] + "..") if len(room.name) > 20 else room.name
        parts.append(
            f'<text x="{x + 8}" y="{y + 36}" font-family="Inter,sans-serif" font-size="10" '
            f'fill="{text_color}">{display_name}</text>'
        )
        if room.has_key and room.explored:
            parts.append(
                f'<text x="{x + node_w - 16}" y="{y + 18}" font-family="monospace" '
                f'font-size="12" fill="#fbbf24" font-weight="bold">K</text>'
            )

    legend_y = max_y - 30
    for i, (color, label) in enumerate(
        [("#7c3aed", "Atual"), ("#3f3f5c", "Explorada"), ("#6b7280", "Oculta"), ("#ef4444", "Trancada")]
    ):
        lx = padding + i * 130
        parts.append(f'<rect x="{lx}" y="{legend_y}" width="12" height="12" rx="3" fill="{color}"/>')
        parts.append(
            f'<text x="{lx + 18}" y="{legend_y + 10}" font-family="Inter,sans-serif" '
            f'font-size="10" fill="#6b7280">{label}</text>'
        )

    parts.append('</svg>')
    return "\n".join(parts)
