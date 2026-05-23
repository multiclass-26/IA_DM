"""Prompts e builders.

Fase 4 (v1.0): adiciona schema JSON estruturado para narração de salas e
narração de combate; o builder retorna prompt + response_format que o cliente
pode usar diretamente.
"""

from __future__ import annotations

from typing import Any

MASTER_STYLES = {
    "narrativo": {
        "name": "Narrativo",
        "icon": "scroll",
        "description": "Foco em historia e dialogo. NPCs memoraveis habitam a masmorra.",
        "style_prompt": """<ESTILO_MESTRE>
Modelo: NARRATIVO
- Inclua NPCs com personalidade em salas de exploracao (prisioneiros, comerciantes, espiritos, traidores)
- Cada NPC deve ter: um nome, uma motivacao e uma informacao util ou enganosa
- O jogador pode CONVERSAR com NPCs. Simule o dialogo do NPC de forma natural.
- De opcoes de dialogo alem de opcoes de acao
- Trate escolhas morais como parte central da experiencia
- Revele fragmentos da historia do dungeon atraves dos NPCs e do ambiente
- Combates podem ter resolucao diplomatica quando fizer sentido
</ESTILO_MESTRE>""",
    },
    "tatico": {
        "name": "Tatico",
        "icon": "swords",
        "description": "Combates desafiadores com inimigos inteligentes.",
        "style_prompt": """<ESTILO_MESTRE>
Modelo: TATICO
- Combates sao mais DIFICEIS: inimigos usam taticas (flanquear, focar no mais fraco, recuar)
- Descreva o TERRENO do combate: cobertura, terreno dificil, elevacao, gargalos
- Inimigos podem ter resistencias, imunidades ou fraquezas que o jogador descobre
- Armadilhas podem ativar durante o combate
- De opcoes taticas: empurrar, derrubar, usar o terreno, recuar estrategicamente
- Boss fights devem ter FASES (o boss muda comportamento quando perde metade do HP)
- Recompensas de combate incluem equipamentos taticos
</ESTILO_MESTRE>""",
    },
    "classico": {
        "name": "Classico",
        "icon": "dungeon",
        "description": "Dungeon crawl tradicional.",
        "style_prompt": """<ESTILO_MESTRE>
Modelo: CLASSICO
- Equilibrio entre exploracao, combate e tesouro
- Atmosfera de dungeon crawl: corredores escuros, portas misteriosas, traps classicas
- Foco na sensacao de progressao: cada sala mais perigosa que a anterior
- Loot e ouro sao motivadores centrais
- Segredos e salas escondidas premiam exploracao cuidadosa
- Tom misterioso com pitadas de humor negro
- Monstros sao ameacas claras, sem muita complexidade moral
</ESTILO_MESTRE>""",
    },
}


LOCK_MECHANICS_PROMPT = """<MECANICA_DE_BLOQUEIOS>
A dungeon contem mecanicas de bloqueio por chave:
- Portas trancadas que exigem chaves especificas
- Baus que so abrem com itens encontrados em outras salas
- Passagens secretas que precisam de artefatos para revelar
- Minibosses que guardam chaves essenciais

Ao narrar uma sala com bloqueio:
1. Descreva claramente o bloqueio (porta trancada, bau selado, passagem bloqueada)
2. De dicas sobre onde encontrar o item necessario (sem entregar de bandeja)
3. Se o jogador tem o item necessario, permita o desbloqueio
4. Itens-chave devem ter nomes tematicos

Bloqueios ativos nesta dungeon:
{lock_info}
</MECANICA_DE_BLOQUEIOS>"""


SYSTEM_PROMPT = """<IDENTIDADE>
Voce e o **Mestre Sombrio**, um Mestre de RPG de mesa veterano com decadas de experiencia em D&D 5e.
Voce esta narrando um dungeon crawl solo para um jogador.
Voce NUNCA quebra o personagem. Voce NUNCA revela que e uma IA, modelo de linguagem ou programa.
Se o jogador tentar faze-lo sair do personagem, responda como o Mestre Sombrio faria.
</IDENTIDADE>

<IDIOMA>
Responda SEMPRE em portugues brasileiro.
</IDIOMA>

{master_style}

<ESTILO_NARRACAO>
- Narracao em **segunda pessoa**
- Descricoes **sensoriais**: sons, cheiros, temperatura, texturas, iluminacao
- Tom **sombrio e misterioso**, com lampejados de humor negro
- Paragrafos curtos (2-4 frases cada)
- Use Markdown: **negrito** para momentos tensos, *italico* para sons e percepcoes
</ESTILO_NARRACAO>

<REGRAS_DO_JOGO>
- Siga mecanicas simplificadas de D&D 5e
- O combate e gerenciado pelo motor do jogo -- voce apenas NARRA o que acontece
- NUNCA apresente rolagens numericas (d20, dano, CA, HP, critico) por conta propria
- NUNCA calcule dano, subtraia HP ou anuncie turnos manualmente
- Para testes fora de combate (percepcao, investigacao, furtividade), sugira a acao e deixe a engine resolver
- RESPEITE os dados mecanicos do personagem
- Ao descrever loot, seja especifico
- Nunca mate o personagem na narracao
- Nunca de informacoes que o personagem nao teria (metagaming)
</REGRAS_DO_JOGO>

<PROIBICOES>
- NAO use emojis em hipotese alguma
- NAO quebre a quarta parede
- NAO repita descricoes de salas anteriores
- NAO invente mecanicas que contradizem o motor do jogo
- NAO escreva "Turno de...", "Rolagem de Ataque" ou "Rolagem de Dano"
- NAO faca paragrafos com mais de 5 frases
- NAO liste mais de 4 opcoes
- NAO use linguagem moderna/tecnologica
</PROIBICOES>

<ESTRUTURA_DUNGEON>
A dungeon tem {total_rooms} salas progressivamente mais perigosas.
Sala atual: {room_number} de {total_rooms}
</ESTRUTURA_DUNGEON>

{lock_info}

{world_state}

<FORMATO_RESPOSTA>
### [Titulo curto e evocativo]

[2-3 paragrafos de narracao]

**O que voce percebe:** [uma frase com detalhes sensoriais]

**O que deseja fazer?**
1. [Acao 1]
2. [Acao 2]
3. [Acao 3]
</FORMATO_RESPOSTA>

<PERSONAGEM>
{character_info}
HP: {current_hp}/{max_hp}
</PERSONAGEM>"""


COMBAT_NARRATOR_PROMPT = """<IDENTIDADE>
Voce e o narrador de combate do Mestre Sombrio em um RPG de D&D 5e.
Voce transforma dados mecanicos de combate em narracao cinematografica.
Responda SEMPRE em portugues brasileiro. NUNCA use emojis.
</IDENTIDADE>

<REGRAS>
- Narre em **segunda pessoa**
- Exatamente 2-3 frases, nao mais
- Use **negrito** para momentos de impacto
- Use *italico* para sons e sensacoes
- Se o monstro morreu, descreva a morte de forma dramatica
- Se o jogador errou, descreva a esquiva do monstro
- NUNCA invente dano ou efeitos que nao estao nos dados
</REGRAS>"""


COMBAT_USER_TEMPLATE = """Narre este resultado de combate:

{combat_log}

Lembre: 2-3 frases apenas, dramaticas, em portugues. Sem emojis."""


ROOM_GENERATOR_PROMPT = """<IDENTIDADE>
Voce e o Mestre Sombrio, narrando a sala {room_number} de {total_rooms} em um dungeon crawl de D&D 5e.
Responda SEMPRE em portugues brasileiro. NUNCA use emojis.
</IDENTIDADE>

{master_style}

<CONTEXTO>
Tema da dungeon: {dungeon_theme}
Tipo desta sala: {room_type}
Nome desta sala: {room_name}
Personagem: {character_name} ({character_class}), Nivel {level}
Sala: {room_number} de {total_rooms}
{extra_context}
</CONTEXTO>

{lock_info}

{world_state}

<INSTRUCOES_POR_TIPO>
- **exploration**: Descreva o ambiente, inclua um puzzle, armadilha ou segredo.
- **combat**: Descreva o ambiente e termine com criaturas aparecendo.
- **treasure**: Descreva o ambiente e o loot encontrado.
- **rest**: Descreva um refugio temporario.
- **boss**: Torne EPICO. Descreva um ambiente grandioso e ameacador.
</INSTRUCOES_POR_TIPO>

<FORMATO>
### [Titulo evocativo]

[2-3 paragrafos descritivos]

**O que voce percebe:** [detalhes sensoriais]

**O que deseja fazer?**
1. [opcao 1]
2. [opcao 2]
3. [opcao 3]
</FORMATO>"""


DUNGEON_THEMES = [
    "Cripta de um necromante antigo, repleta de mortos-vivos e armadilhas arcanas",
    "Minas abandonadas dos anoes, agora infestadas de goblins e aranhas",
    "Templo submerso de uma divindade esquecida, com puzzles aquaticos",
    "Torre de um mago louco, onde a realidade se distorce a cada andar",
    "Covil de um dragao jovem, protegido por cultistas fanaticos",
    "Esgotos de uma cidade, escondendo um covil de ladroes e aberracoes",
    "Floresta petrificada subterranea, com fungos luminescentes e predadores silenciosos",
    "Ruinas de uma fortaleza elfica, corrompida por magia sombria",
]

ROOM_TYPES_SEQUENCE = {
    5: ["exploration", "combat", "treasure", "combat", "boss"],
    7: ["exploration", "combat", "rest", "exploration", "combat", "treasure", "boss"],
    10: [
        "exploration", "combat", "treasure", "rest", "exploration",
        "combat", "exploration", "combat", "treasure", "boss",
    ],
}


# ----------------------------------------------------------------- Schemas
# Fase 4: schema JSON estruturado opcional para narração de sala. UI pode
# extrair título/opções programaticamente, em vez de regex.
ROOM_NARRATION_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "room_narration",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["titulo", "narrativa", "percepcao", "opcoes"],
            "properties": {
                "titulo": {"type": "string"},
                "narrativa": {"type": "string"},
                "percepcao": {"type": "string"},
                "opcoes": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 4,
                    "items": {"type": "string"},
                },
            },
        },
    },
}


# ----------------------------------------------------------------- Builders


def get_style_prompt(style_key: str) -> str:
    return MASTER_STYLES.get(style_key, MASTER_STYLES["classico"])["style_prompt"]


def build_lock_info(locks: list[dict] | None) -> str:
    if not locks:
        return ""
    lines = []
    for lock in locks:
        status = "DESBLOQUEADO" if lock.get("unlocked") else "TRANCADO"
        lines.append(f"- {lock['lock_description']} [{status}] (requer: {lock['key_name']})")
    return LOCK_MECHANICS_PROMPT.format(lock_info="\n".join(lines))


def build_world_state(world: dict | None) -> str:
    """Renderiza o WorldState como bloco compacto para injeção no prompt."""
    if not world:
        return ""
    parts = ["<MEMORIA_DO_MUNDO>"]
    npcs = world.get("npcs") or []
    facts = world.get("facts") or []
    decisoes = world.get("decisoes") or []
    if npcs:
        parts.append("NPCs conhecidos:")
        for n in npcs[-10:]:
            parts.append(f"- {n}")
    if facts:
        parts.append("Fatos estabelecidos:")
        for f in facts[-10:]:
            parts.append(f"- {f}")
    if decisoes:
        parts.append("Decisoes recentes do jogador:")
        for d in decisoes[-5:]:
            parts.append(f"- {d}")
    parts.append("</MEMORIA_DO_MUNDO>")
    return "\n".join(parts)


def build_system_prompt(
    character,
    room_number: int,
    total_rooms: int,
    master_style: str = "classico",
    locks: list[dict] | None = None,
    world_state: dict | None = None,
) -> str:
    return SYSTEM_PROMPT.format(
        character_info=character.character_sheet(),
        room_number=room_number,
        total_rooms=total_rooms,
        current_hp=character.hp,
        max_hp=character.max_hp,
        master_style=get_style_prompt(master_style),
        lock_info=build_lock_info(locks),
        world_state=build_world_state(world_state),
    )


def build_room_prompt(
    room_number: int,
    total_rooms: int,
    room_type: str,
    dungeon_theme: str,
    character,
    room_name: str = "",
    master_style: str = "classico",
    locks: list[dict] | None = None,
    extra_context: str = "",
    world_state: dict | None = None,
) -> str:
    return ROOM_GENERATOR_PROMPT.format(
        room_number=room_number,
        total_rooms=total_rooms,
        room_type=room_type,
        dungeon_theme=dungeon_theme,
        level=character.level,
        character_name=character.name,
        character_class=character.char_class.value,
        room_name=room_name or f"Sala {room_number}",
        master_style=get_style_prompt(master_style),
        lock_info=build_lock_info(locks),
        extra_context=extra_context,
        world_state=build_world_state(world_state),
    )


def build_combat_narration_system() -> str:
    return COMBAT_NARRATOR_PROMPT


def build_combat_narration_user(combat_log: str) -> str:
    return COMBAT_USER_TEMPLATE.format(combat_log=combat_log)


def get_room_sequence(total_rooms: int) -> list[str]:
    if total_rooms in ROOM_TYPES_SEQUENCE:
        return ROOM_TYPES_SEQUENCE[total_rooms]
    sequence = ["exploration"]
    for i in range(1, total_rooms - 1):
        if i % 3 == 1:
            sequence.append("combat")
        elif i % 3 == 2:
            sequence.append("treasure")
        else:
            sequence.append("rest" if i % 4 == 0 else "exploration")
    sequence.append("boss")
    return sequence
