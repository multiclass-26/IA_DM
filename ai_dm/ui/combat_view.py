"""Componentes visuais da tela de combate."""

from __future__ import annotations

import re

import streamlit as st

from ai_dm.domain.character import CLASS_DATA, Character
from ai_dm.domain.monster import Monster


def _compact_text(text: str, *, max_len: int = 180) -> str:
    cleaned = re.sub(r"[*_`#>-]", "", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def render_combat_hud(character: Character, monsters: list[Monster], current_room: int, total_rooms: int) -> None:
    alive = [monster for monster in monsters if monster.is_alive()]
    target_names = ", ".join(monster.name for monster in alive[:2])
    if len(alive) > 2:
        target_names += f" e mais {len(alive) - 2}"

    st.markdown('<div class="combat-shell">', unsafe_allow_html=True)
    st.markdown(
        (
            '<div class="combat-header">'
            '<div>'
            '<div class="combat-eyebrow">Combate tático</div>'
            f'<h2>{len(alive)} inimigo(s) à frente</h2>'
            f'<p>Turno do jogador • ameaça atual: {target_names}</p>'
            '</div>'
            '<div class="combat-badge combat-badge-danger">Em combate</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    primary_threat = alive[0].name if alive else "Nenhuma"

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            f'<div class="combat-stat-card"><span>Inimigos vivos</span><strong>{len(alive)}</strong></div>',
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            f'<div class="combat-stat-card"><span>Ameaça principal</span><strong>{primary_threat}</strong></div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def render_enemy_cards(monsters: list[Monster], selected_target: int) -> None:
    st.markdown("### Inimigos")
    cols = st.columns(max(1, min(3, len(monsters))))

    for idx, monster in enumerate(monsters):
        card_class = "combat-enemy-card combat-enemy-card-selected" if idx == selected_target else "combat-enemy-card"
        hp_pct = monster.hp / max(monster.max_hp, 1)
        with cols[idx % len(cols)]:
            st.markdown(
                (
                    f'<div class="{card_class}">'
                    f'<div class="combat-card-title">{monster.name}</div>'
                    f'<div class="combat-card-meta">CA {monster.ac}</div>'
                    f'<div class="combat-card-badge">{("Alvo atual" if idx == selected_target else "Disponível")}</div>'
                    '</div>'
                ),
                unsafe_allow_html=True,
            )
            st.progress(hp_pct, text=f"HP: {monster.hp}/{monster.max_hp}")
            if idx == selected_target and monster.special:
                st.caption(f"Especial: {monster.special}")


def render_action_panel(character: Character, monsters: list[Monster]) -> tuple[str | None, Monster | None]:
    st.markdown("### Seu turno")
    st.caption("Escolha um alvo, execute sua ação e acompanhe a resolução logo abaixo.")

    options = list(range(len(monsters)))
    if not options:
        return None, None

    if st.session_state.get("combat_selected_target", 0) not in options:
        st.session_state.combat_selected_target = options[0]

    st.selectbox(
        "Alvo",
        options,
        key="combat_selected_target",
        format_func=lambda i: f"{monsters[i].name} • HP {monsters[i].hp}/{monsters[i].max_hp} • CA {monsters[i].ac}",
    )
    selected_monster = monsters[st.session_state.combat_selected_target]
    st.caption(f"Alvo atual: {selected_monster.name} • HP {selected_monster.hp}/{selected_monster.max_hp}")

    special_label = CLASS_DATA[character.char_class]["special"]
    special_label = special_label.split("**")[1] if "**" in special_label else "Especial"
    can_use = character.special_uses > 0

    st.markdown('<div class="combat-action-group-label">Ofensivas</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Atacar", type="primary", use_container_width=True, key="combat_attack_action"):
            return "attack", selected_monster
    with col_b:
        if st.button(
            f"{special_label} ({character.special_uses})",
            use_container_width=True,
            disabled=not can_use,
            key="combat_special_action",
        ):
            return "special", selected_monster

    st.markdown('<div class="combat-action-group-label">Utilidade e risco</div>', unsafe_allow_html=True)
    col_c, col_d, col_e = st.columns(3)
    with col_c:
        if st.button("Poção", use_container_width=True, key="combat_potion_action"):
            return "potion", None
    with col_d:
        if st.button("Ver ficha", use_container_width=True, key="combat_sheet_action"):
            return "sheet", None
    with col_e:
        if st.button("Fugir", use_container_width=True, key="combat_flee_action"):
            return "flee", None

    return None, selected_monster


def render_round_summary(summary: str, combat_log: list[str]) -> None:
    st.markdown("### Resolução da rodada")
    if summary:
        st.markdown('<div class="combat-summary-card">', unsafe_allow_html=True)
        st.markdown(summary)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Nenhuma ação resolvida ainda. Escolha seu alvo e execute o primeiro turno.")

    st.markdown("### Últimos eventos")
    if not combat_log:
        st.caption("Os eventos do combate aparecerão aqui assim que o primeiro golpe acontecer.")
        return

    for entry in combat_log[-4:][::-1]:
        st.markdown(
            (
                '<div class="combat-log-item">'
                f'{_compact_text(entry)}'
                '</div>'
            ),
            unsafe_allow_html=True,
        )


def render_combat_journal(messages: list[dict]) -> None:
    recent = [msg for msg in messages if msg.get("role") in {"assistant", "system"}][-4:]
    with st.expander("Narração e eventos recentes", expanded=False):
        if not recent:
            st.caption("Sem eventos recentes.")
            return
        for msg in recent:
            role_label = "Mestre" if msg.get("role") == "assistant" else "Sistema"
            st.caption(role_label)
            st.markdown(msg.get("content", ""))