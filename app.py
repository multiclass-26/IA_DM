"""
AI Dungeon Master -- Streamlit App
Um dungeon crawl solo de D&D com IA agindo como Mestre de RPG.
"""

import csv
import io
import json
import os
import random
import re
import time
from pathlib import Path
import streamlit as st

from game_engine import (
    Character, CharClass, Race, Monster,
    CLASS_DATA, RACE_DATA, ABILITY_FULL,
    roll, roll_check, ability_modifier,
    resolve_player_attack, resolve_monster_attack, use_potion,
    get_encounter_for_level, MONSTER_TEMPLATES,
)
from prompts import (
    build_system_prompt, build_room_prompt,
    build_combat_narration_system, build_combat_narration_user,
    get_room_sequence, DUNGEON_THEMES, MASTER_STYLES,
    get_style_prompt, build_lock_info,
)
from llm_client import chat_completion
from dungeon_map import (
    generate_dungeon_map, render_map_svg, get_lock_status_text,
    DungeonMap, DungeonRoom,
)

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Dungeon Master",
    page_icon="d20",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ai_dm.ui.styles import inject as _inject_styles
_inject_styles()


SAVE_DIR = Path(__file__).parent / "saves"
SAVE_FILE = SAVE_DIR / "savegame.json"
MAX_CONTEXT_MESSAGES = 24
SUMMARY_TRIGGER_MESSAGES = 40
SUMMARY_MIN_CHUNK = 12
MAX_STORED_MESSAGES = 120
MIN_PRUNE_BATCH = 16
SYSTEM_RNG = random.SystemRandom()


def _read_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
        return str(value) if value else ""
    except Exception:
        return ""


def _default_gemini_api_key() -> str:
    return (
        _read_secret("GEMINI_API_KEY")
        or _read_secret("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY", "")
        or os.getenv("GOOGLE_API_KEY", "")
    )


def _normalize_api_key(value: str) -> str:
    key = (value or "").strip()
    key = re.sub(r"\s+", "", key)
    if len(key) >= 2 and key[0] == key[-1] and key[0] in ["'", '"', "`"]:
        key = key[1:-1]
    return key


def _serialize_character(char: Character | None) -> dict | None:
    if not char:
        return None
    return {
        "name": char.name,
        "race": char.race.name,
        "char_class": char.char_class.name,
        "level": char.level,
        "abilities": char.abilities,
        "hp": char.hp,
        "max_hp": char.max_hp,
        "ac": char.ac,
        "inventory": char.inventory,
        "gold": char.gold,
        "xp": char.xp,
        "special_uses": char.special_uses,
        "max_special_uses": char.max_special_uses,
        "conditions": char.conditions,
        "keys": char.keys,
    }


def _deserialize_character(data: dict | None) -> Character | None:
    if not data:
        return None

    char = Character(
        name=data["name"],
        race=Race[data["race"]],
        char_class=CharClass[data["char_class"]],
    )
    char.level = data.get("level", char.level)
    char.abilities = data.get("abilities", char.abilities)
    char.max_hp = data.get("max_hp", char.max_hp)
    char.hp = data.get("hp", char.hp)
    char.ac = data.get("ac", char.ac)
    char.inventory = data.get("inventory", char.inventory)
    char.gold = data.get("gold", char.gold)
    char.xp = data.get("xp", char.xp)
    char.special_uses = data.get("special_uses", char.special_uses)
    char.max_special_uses = data.get("max_special_uses", char.max_special_uses)
    char.conditions = data.get("conditions", char.conditions)
    char.keys = data.get("keys", char.keys)
    return char


def _serialize_monster(monster: Monster) -> dict:
    return {
        "name": monster.name,
        "hp": monster.hp,
        "max_hp": monster.max_hp,
        "ac": monster.ac,
        "attack_bonus": monster.attack_bonus,
        "damage": monster.damage,
        "xp_reward": monster.xp_reward,
        "description": monster.description,
        "special": monster.special,
    }


def _deserialize_monster(data: dict) -> Monster:
    return Monster(
        name=data["name"],
        hp=data["hp"],
        max_hp=data["max_hp"],
        ac=data["ac"],
        attack_bonus=data["attack_bonus"],
        damage=data["damage"],
        xp_reward=data["xp_reward"],
        description=data.get("description", ""),
        special=data.get("special", ""),
    )


def _serialize_dungeon_map(dmap: DungeonMap | None) -> dict | None:
    if not dmap:
        return None
    return {
        "current_room": dmap.current_room,
        "locks": dmap.locks,
        "rooms": [
            {
                "number": room.number,
                "room_type": room.room_type,
                "name": room.name,
                "connections": room.connections,
                "explored": room.explored,
                "locked": room.locked,
                "lock_info": room.lock_info,
                "has_key": room.has_key,
            }
            for room in dmap.rooms
        ],
    }


def _deserialize_dungeon_map(data: dict | None) -> DungeonMap | None:
    if not data:
        return None

    rooms = [
        DungeonRoom(
            number=room["number"],
            room_type=room["room_type"],
            name=room["name"],
            connections=room.get("connections", []),
            explored=room.get("explored", False),
            locked=room.get("locked", False),
            lock_info=room.get("lock_info", {}),
            has_key=room.get("has_key", ""),
        )
        for room in data.get("rooms", [])
    ]

    return DungeonMap(
        rooms=rooms,
        locks=data.get("locks", []),
        current_room=data.get("current_room", 1),
    )


def _build_save_payload() -> dict:
    return {
        "game_phase": st.session_state.game_phase,
        "character": _serialize_character(st.session_state.character),
        "messages": st.session_state.messages,
        "combat_monsters": [_serialize_monster(m) for m in st.session_state.combat_monsters],
        "combat_turn": st.session_state.combat_turn,
        "current_room": st.session_state.current_room,
        "total_rooms": st.session_state.total_rooms,
        "room_sequence": st.session_state.room_sequence,
        "dungeon_theme": st.session_state.dungeon_theme,
        "ollama_model": st.session_state.ollama_model,
        "ollama_url": st.session_state.ollama_url,
        "gemini_model": st.session_state.gemini_model,
        "gemini_api_key": "",
        "llm_provider": st.session_state.llm_provider,
        "temperature": st.session_state.temperature,
        "master_style": st.session_state.master_style,
        "dungeon_map": _serialize_dungeon_map(st.session_state.dungeon_map),
        "has_map": st.session_state.has_map,
        "show_map": False,
        "combat_log": st.session_state.combat_log,
        "rooms_cleared": st.session_state.rooms_cleared,
        "game_log": st.session_state.game_log,
        "story_summary": st.session_state.story_summary,
        "summary_cursor": st.session_state.summary_cursor,
        "llm_metrics": st.session_state.llm_metrics,
        "combat_key_reward": st.session_state.get("combat_key_reward", ""),
    }


def save_game_state(file_path: Path = SAVE_FILE) -> tuple[bool, str]:
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _build_save_payload()
        file_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return True, f"Jogo salvo em: {file_path}"
    except Exception as exc:
        return False, f"Falha ao salvar jogo: {exc}"


def load_game_state(file_path: Path = SAVE_FILE) -> tuple[bool, str]:
    if not file_path.exists():
        return False, f"Arquivo de save nao encontrado: {file_path}"

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))

        st.session_state.game_phase = data.get("game_phase", "setup")
        st.session_state.character = _deserialize_character(data.get("character"))
        st.session_state.messages = data.get("messages", [])
        st.session_state.combat_monsters = [_deserialize_monster(m) for m in data.get("combat_monsters", [])]
        st.session_state.combat_turn = data.get("combat_turn", "player")
        st.session_state.current_room = data.get("current_room", 0)
        st.session_state.total_rooms = data.get("total_rooms", 7)
        st.session_state.room_sequence = data.get("room_sequence", [])
        st.session_state.dungeon_theme = data.get("dungeon_theme", "")
        st.session_state.ollama_model = data.get("ollama_model", "llama3.1")
        st.session_state.ollama_url = data.get("ollama_url", "http://localhost:11434/v1")
        gemini_model = data.get("gemini_model", "gemini-2.5-flash-lite") or "gemini-2.5-flash-lite"
        # Migra modelos desativados.
        if gemini_model.strip() == "gemini-2.0-flash":
            gemini_model = "gemini-2.5-flash-lite"
        st.session_state.gemini_model = gemini_model
        # Bug-fix v1.0: nunca carregar API key do save. Sempre do env/secret/sessão.
        st.session_state.gemini_api_key = _normalize_api_key(
            st.session_state.gemini_api_key or _default_gemini_api_key()
        )
        st.session_state.llm_provider = data.get("llm_provider", "ollama")
        st.session_state.temperature = data.get("temperature", 0.7)
        st.session_state.master_style = data.get("master_style", "classico")
        st.session_state.dungeon_map = _deserialize_dungeon_map(data.get("dungeon_map"))
        st.session_state.has_map = data.get("has_map", False)
        st.session_state.show_map = False
        st.session_state.combat_log = data.get("combat_log", [])
        st.session_state.rooms_cleared = data.get("rooms_cleared", 0)
        st.session_state.game_log = data.get("game_log", [])
        st.session_state.story_summary = data.get("story_summary", "")
        st.session_state.summary_cursor = data.get("summary_cursor", 0)
        st.session_state.llm_metrics = data.get("llm_metrics", [])
        st.session_state["combat_key_reward"] = data.get("combat_key_reward", "")
        st.session_state.connection_last_ok = 0.0
        st.session_state.connection_fingerprint = ""
        return True, "Jogo carregado com sucesso."
    except Exception as exc:
        return False, f"Falha ao carregar save: {exc}"


def _record_llm_metric(call_type: str, elapsed_s: float, success: bool,
                       prompt_chars: int, response_chars: int, error: str = "",
                       provider_override: str | None = None,
                       model_override: str | None = None):
    provider = provider_override or st.session_state.llm_provider
    if model_override:
        model = model_override
    else:
        model = st.session_state.ollama_model if provider == "ollama" else st.session_state.gemini_model
    st.session_state.llm_metrics.append({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "provider": provider,
        "model": model,
        "call_type": call_type,
        "elapsed_s": round(elapsed_s, 3),
        "success": success,
        "prompt_chars": prompt_chars,
        "response_chars": response_chars,
        "error": error,
    })


def _metrics_csv() -> str:
    if not st.session_state.llm_metrics:
        return ""

    output = io.StringIO()
    fieldnames = [
        "ts", "provider", "model", "call_type", "elapsed_s",
        "success", "prompt_chars", "response_chars", "error",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in st.session_state.llm_metrics:
        writer.writerow(row)
    return output.getvalue()


# ============================================================
# SESSION STATE INIT
# ============================================================

def init_session_state():
    defaults = {
        "game_phase": "setup",
        "character": None,
        "messages": [],
        "combat_monsters": [],
        "combat_turn": "player",
        "current_room": 0,
        "total_rooms": 7,
        "room_sequence": [],
        "dungeon_theme": "",
        "llm_provider": "ollama",
        "ollama_model": "llama3.1",
        "ollama_url": "http://localhost:11434/v1",
        "gemini_model": "gemini-2.5-flash-lite",
        "gemini_api_key": _normalize_api_key(_default_gemini_api_key()),
        "temperature": 0.7,
        "master_style": "classico",
        "dungeon_map": None,
        "has_map": False,
        "show_map": False,
        "combat_log": [],
        "rooms_cleared": 0,
        "game_log": [],
        "story_summary": "",
        "summary_cursor": 0,
        "llm_metrics": [],
        "combat_key_reward": "",
        "connection_last_ok": 0.0,
        "connection_fingerprint": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()


# ============================================================
# LLM HELPER
# ============================================================

def _provider_config() -> tuple[str, str, str | None, str | None]:
    provider = st.session_state.llm_provider
    if provider == "gemini":
        model = (st.session_state.gemini_model or "gemini-2.5-flash-lite").strip()
        api_key = _normalize_api_key(st.session_state.gemini_api_key or "")
        st.session_state.gemini_api_key = api_key
        return provider, model, None, api_key

    model = (st.session_state.ollama_model or "llama3.1").strip()
    base_url = (st.session_state.ollama_url or "http://localhost:11434/v1").strip()
    return "ollama", model, base_url, None


def _check_llm_connection() -> str | None:
    """Verifica conectividade com o provedor selecionado."""
    import urllib.error
    import urllib.request

    provider, _, base_url, api_key = _provider_config()
    fingerprint = f"{provider}|{base_url or ''}|{(api_key or '')[:6]}"
    now_ts = time.time()
    if (
        st.session_state.connection_fingerprint == fingerprint
        and (now_ts - st.session_state.connection_last_ok) < 45
    ):
        return None

    if provider == "ollama":
        base = (base_url or "").replace("/v1", "")
        try:
            req = urllib.request.Request(f"{base}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5):
                pass
            st.session_state.connection_last_ok = now_ts
            st.session_state.connection_fingerprint = fingerprint
            return None
        except urllib.error.URLError:
            return (
                "**Nao foi possivel conectar ao Ollama.**\n\n"
                "Verifique se:\n"
                "1. O Ollama esta instalado (https://ollama.com/download)\n"
                "2. O servico esta rodando (`ollama serve` no terminal)\n"
                "3. Voce baixou um modelo (`ollama pull llama3.1`)\n"
                f"4. A URL esta correta: {st.session_state.ollama_url}"
            )
        except Exception as exc:
            return f"**Erro ao verificar Ollama:** {exc}"

    if not api_key:
        return (
            "**API key do Gemini nao configurada.**\n\n"
            "1. Crie sua chave em https://aistudio.google.com/app/apikey\n"
            "2. Cole a chave no campo 'Gemini API Key' na barra lateral"
        )

    try:
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/openai/models",
            method="GET",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=8):
            pass
        st.session_state.connection_last_ok = now_ts
        st.session_state.connection_fingerprint = fingerprint
        return None
    except urllib.error.HTTPError as exc:
        message = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
            match = re.search(r'"message"\s*:\s*"([^"]+)"', body)
            if match:
                message = match.group(1)
        except Exception:
            message = ""

        if message:
            if len(message) > 220:
                message = message[:220] + "..."
            return f"**Falha ao validar API key do Gemini:** HTTP {exc.code} - {message}"

        return f"**Falha ao validar API key do Gemini:** HTTP {exc.code}."
    except Exception as exc:
        return f"**Erro ao verificar Gemini:** {exc}"


def _build_authoritative_state() -> str:
    char = st.session_state.character
    dmap = st.session_state.dungeon_map

    if not char:
        return ""

    current_room = st.session_state.current_room
    room_name = ""
    if dmap:
        room = dmap.get_room(current_room)
        room_name = room.name if room else ""

    inv = ", ".join(char.inventory) if char.inventory else "vazio"
    keys = ", ".join(char.keys) if char.keys else "nenhuma"

    return (
        "<ESTADO_AUTORITATIVO>\n"
        "Use este estado como fonte de verdade e NAO contradiga esses dados.\n"
        f"Sala atual: {current_room}/{st.session_state.total_rooms} ({room_name})\n"
        f"HP: {char.hp}/{char.max_hp}\n"
        f"CA: {char.ac}\n"
        f"Nivel: {char.level}\n"
        f"Ouro: {char.gold}\n"
        f"Inventario: {inv}\n"
        f"Chaves: {keys}\n"
        "</ESTADO_AUTORITATIVO>"
    )


def _maybe_update_story_summary():
    total_messages = len(st.session_state.messages)
    if total_messages < SUMMARY_TRIGGER_MESSAGES:
        return

    cutoff = total_messages - MAX_CONTEXT_MESSAGES
    start = st.session_state.summary_cursor
    if cutoff <= start:
        return

    chunk = st.session_state.messages[start:cutoff]
    if len(chunk) < SUMMARY_MIN_CHUNK:
        return

    compact_lines = []
    for msg in chunk:
        role = msg.get("role", "assistant")
        content = (msg.get("content", "") or "").replace("\n", " ").strip()
        compact_lines.append(f"{role}: {content[:320]}")

    provider, model, base_url, api_key = _provider_config()
    prev_summary = st.session_state.story_summary or "Sem resumo anterior."
    user_prompt = (
        "Atualize o resumo persistente de uma campanha de RPG. "
        "Mantenha apenas fatos que impactam continuidade narrativa e mecanica.\n\n"
        f"Resumo anterior:\n{prev_summary}\n\n"
        "Novos eventos:\n"
        + "\n".join(compact_lines)
        + "\n\n"
        "Responda em ate 10 linhas, objetivo e sem floreio."
    )

    start_time = time.perf_counter()
    try:
        summary = chat_completion(
            provider=provider,
            model=model,
            system_prompt="Voce e um resumidor de estado narrativo para RPG de mesa.",
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.2,
            max_tokens=420,
            base_url=base_url,
            api_key=api_key,
            retries=1,
        )
        elapsed = time.perf_counter() - start_time
        _record_llm_metric(
            call_type="summary",
            elapsed_s=elapsed,
            success=True,
            prompt_chars=len(user_prompt),
            response_chars=len(summary),
            provider_override=provider,
            model_override=model,
        )
        st.session_state.story_summary = summary
        st.session_state.summary_cursor = cutoff
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        _record_llm_metric(
            call_type="summary",
            elapsed_s=elapsed,
            success=False,
            prompt_chars=len(user_prompt),
            response_chars=0,
            error=str(exc),
            provider_override=provider,
            model_override=model,
        )


def _build_history(user_message: str) -> list[dict]:
    history = []
    if st.session_state.story_summary:
        history.append({
            "role": "system",
            "content": "Resumo da aventura ate aqui:\n" + st.session_state.story_summary,
        })

    history.append({
        "role": "system",
        "content": _build_vital_reminder(),
    })

    start = max(st.session_state.summary_cursor, len(st.session_state.messages) - MAX_CONTEXT_MESSAGES)
    for msg in st.session_state.messages[start:]:
        history.append({"role": msg["role"], "content": msg["content"]})

    if user_message:
        history.append({"role": "user", "content": user_message})
    return history


def _build_vital_reminder() -> str:
    char = st.session_state.character
    dmap = st.session_state.dungeon_map

    if not char:
        return "<LEMBRETES_VITAIS>Sem personagem ativo.</LEMBRETES_VITAIS>"

    inv = ", ".join(char.inventory[:12]) if char.inventory else "vazio"
    keys = ", ".join(char.keys) if char.keys else "nenhuma"

    room_label = f"{st.session_state.current_room}/{st.session_state.total_rooms}"
    explored_hint = ""
    lock_hint = ""
    conn_hint = ""

    if dmap:
        explored = [f"{r.number}-{r.name}" for r in dmap.rooms if r.explored]
        explored_tail = explored[-4:] if explored else []
        if explored_tail:
            explored_hint = " | Ultimas salas exploradas: " + "; ".join(explored_tail)

        current_room = dmap.get_room(st.session_state.current_room)
        if current_room and current_room.connections:
            conn_hint = " | Conexoes da sala atual: " + ", ".join(str(n) for n in current_room.connections)

        active_locks = [f"Sala {l['lock_room']} requer {l['key_name']}" for l in dmap.locks if not l.get("unlocked")]
        if active_locks:
            lock_hint = " | Bloqueios ativos: " + "; ".join(active_locks[:3])

    return (
        "<LEMBRETES_VITAIS>\n"
        "Preserve continuidade dos fatos, sem recalcular combate fora da engine.\n"
        f"Inventario: {inv} | Chaves: {keys}\n"
        f"Posicao na dungeon: Sala {room_label}{conn_hint}{lock_hint}{explored_hint}\n"
        "</LEMBRETES_VITAIS>"
    )


def _prune_message_history_if_needed():
    messages = st.session_state.messages
    if len(messages) <= MAX_STORED_MESSAGES:
        return

    summary_cursor = st.session_state.summary_cursor
    prune_cap = len(messages) - MAX_CONTEXT_MESSAGES
    prune_upto = min(summary_cursor, prune_cap)

    if prune_upto < MIN_PRUNE_BATCH:
        return

    del messages[:prune_upto]
    st.session_state.summary_cursor = max(0, summary_cursor - prune_upto)


def _is_quota_error(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    return (
        "error code: 429" in lowered
        or "resource_exhausted" in lowered
        or "quota exceeded" in lowered
    )


def _extract_retry_seconds(error_text: str) -> int | None:
    patterns = [
        r"retry in\s*([0-9]+(?:\.[0-9]+)?)s",
        r"retrydelay'?:\s*'([0-9]+)s'",
    ]
    for pattern in patterns:
        match = re.search(pattern, error_text, flags=re.IGNORECASE)
        if match:
            try:
                return max(1, int(float(match.group(1))))
            except Exception:
                return None
    return None


def _friendly_provider_error(exc: Exception, provider: str) -> str:
    raw_error = str(exc)

    if provider == "gemini" and _is_quota_error(raw_error):
        retry_seconds = _extract_retry_seconds(raw_error)
        retry_line = f"4. Aguarde cerca de {retry_seconds}s e tente de novo\n" if retry_seconds else ""
        return (
            "**Gemini indisponivel por cota (HTTP 429).**\n\n"
            "Sua chave/projeto nao tem cota disponivel neste momento (free tier).\n\n"
            "Como resolver:\n"
            "1. Verifique limites em https://ai.dev/rate-limit\n"
            "2. Crie uma nova chave/projeto em https://aistudio.google.com/app/apikey\n"
            "3. Se quiser continuar agora, troque para Ollama na barra lateral\n"
            f"{retry_line}"
            "\nVerifique suas configuracoes na barra lateral."
        )

    if provider == "ollama":
        return (
            "**Falha ao chamar Ollama.**\n\n"
            "Verifique se o servico esta ativo (`ollama serve`) e se o modelo foi baixado (`ollama pull llama3.1`)."
        )

    compact = raw_error.split("\n")[0]
    if len(compact) > 240:
        compact = compact[:240] + "..."
    return f"**Erro ao conectar com a IA:** {compact}\n\nVerifique suas configuracoes na barra lateral."


def _try_ollama_fallback(system_prompt: str, messages: list[dict], max_tokens: int = 1500) -> str | None:
    try:
        response = chat_completion(
            provider="ollama",
            model=(st.session_state.ollama_model or "llama3.1").strip(),
            system_prompt=system_prompt,
            messages=messages,
            temperature=st.session_state.temperature,
            max_tokens=max_tokens,
            base_url=(st.session_state.ollama_url or "http://localhost:11434/v1").strip(),
            retries=1,
        )
        st.session_state.llm_provider = "ollama"
        st.session_state.connection_last_ok = 0.0
        st.session_state.connection_fingerprint = ""
        return response
    except Exception:
        return None


def _try_gemini_alternate_model(system_prompt: str, messages: list[dict],
                                max_tokens: int = 1500) -> tuple[str, str] | None:
    current = (st.session_state.gemini_model or "").strip()
    candidates = [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
    ]
    for candidate in candidates:
        if candidate == current:
            continue
        try:
            response = chat_completion(
                provider="gemini",
                model=candidate,
                system_prompt=system_prompt,
                messages=messages,
                temperature=st.session_state.temperature,
                max_tokens=max_tokens,
                api_key=(st.session_state.gemini_api_key or "").strip(),
                retries=0,
                timeout=40,
            )
            st.session_state.gemini_model = candidate
            st.session_state.connection_last_ok = 0.0
            st.session_state.connection_fingerprint = ""
            return candidate, response
        except Exception:
            continue
    return None


def _check_generation_capability() -> str | None:
    provider, model, base_url, api_key = _provider_config()
    try:
        chat_completion(
            provider=provider,
            model=model,
            system_prompt="Responda apenas com OK.",
            messages=[{"role": "user", "content": "OK"}],
            temperature=0.0,
            max_tokens=8,
            base_url=base_url,
            api_key=api_key,
            retries=0,
            timeout=20,
        )
        return None
    except Exception as exc:
        return _friendly_provider_error(exc, provider)


def _contains_manual_combat_math(text: str) -> bool:
    """Wrapper para guardrails.contains_manual_combat_math (v1.0)."""
    from ai_dm.llm.guardrails import contains_manual_combat_math
    return contains_manual_combat_math(text)


def _combat_consistency_guard_message() -> str:
    return (
        "**Combate detectado fora do motor tatico.**\n\n"
        "Para manter consistencia matematica, rolagens, HP, CA e dano sao calculados somente pela engine.\n\n"
        "Como prosseguir:\n"
        "1. Se estiver em combate, use os botoes: Atacar / Especial / Pocao / Fugir\n"
        "2. Se estiver explorando, descreva uma acao narrativa (investigar, ouvir, abrir, interagir)\n"
        "3. Avance para a proxima sala para acionar encontros de combate gerenciados pelo sistema"
    )


def get_ai_response(user_message: str, system_override: str = None) -> str:
    provider, model, base_url, api_key = _provider_config()
    prompt_chars = 0
    start_time = time.perf_counter()
    history: list[dict] = []
    system = ""
    try:
        err = _check_llm_connection()
        if err:
            return err

        char = st.session_state.character
        dmap = st.session_state.dungeon_map
        locks = dmap.locks if dmap else []

        system = system_override or build_system_prompt(
            char,
            st.session_state.current_room,
            st.session_state.total_rooms,
            master_style=st.session_state.master_style,
            locks=locks,
        )
        system = system + "\n\n" + _build_authoritative_state()

        _maybe_update_story_summary()
        _prune_message_history_if_needed()

        history = _build_history(user_message)
        prompt_chars = len(system) + sum(len(m["content"]) for m in history)

        response = chat_completion(
            provider=provider,
            model=model,
            system_prompt=system,
            messages=history,
            temperature=st.session_state.temperature,
            base_url=base_url,
            api_key=api_key,
            retries=2,
        )
        elapsed = time.perf_counter() - start_time
        _record_llm_metric(
            call_type="story",
            elapsed_s=elapsed,
            success=True,
            prompt_chars=prompt_chars,
            response_chars=len(response),
            provider_override=provider,
            model_override=model,
        )

        if st.session_state.game_phase != "combat" and _contains_manual_combat_math(response):
            _record_llm_metric(
                call_type="story_guardrail",
                elapsed_s=0.0,
                success=False,
                prompt_chars=prompt_chars,
                response_chars=len(response),
                error="Resposta bloqueada por conter calculos de combate fora da engine.",
                provider_override=provider,
                model_override=model,
            )
            return _combat_consistency_guard_message()

        return response

    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        raw_error = str(exc)
        _record_llm_metric(
            call_type="story",
            elapsed_s=elapsed,
            success=False,
            prompt_chars=prompt_chars,
            response_chars=0,
            error=raw_error,
            provider_override=provider,
            model_override=model,
        )

        if provider == "gemini" and _is_quota_error(raw_error):
            alt_start = time.perf_counter()
            alt_result = _try_gemini_alternate_model(system_prompt=system, messages=history, max_tokens=1500)
            if alt_result:
                alt_model, alt_response = alt_result
                alt_elapsed = time.perf_counter() - alt_start
                _record_llm_metric(
                    call_type="story_alt_model",
                    elapsed_s=alt_elapsed,
                    success=True,
                    prompt_chars=prompt_chars,
                    response_chars=len(alt_response),
                    provider_override="gemini",
                    model_override=alt_model,
                )
                return (
                    f"*O modelo Gemini atual ficou sem cota. Continuei automaticamente com {alt_model}.*\n\n"
                    + alt_response
                )

            fallback_start = time.perf_counter()
            fallback_response = _try_ollama_fallback(system_prompt=system, messages=history, max_tokens=1500)
            if fallback_response:
                fallback_elapsed = time.perf_counter() - fallback_start
                _record_llm_metric(
                    call_type="story_fallback",
                    elapsed_s=fallback_elapsed,
                    success=True,
                    prompt_chars=prompt_chars,
                    response_chars=len(fallback_response),
                    provider_override="ollama",
                    model_override=st.session_state.ollama_model,
                )
                return (
                    "*Gemini ficou sem cota (429). Mudei automaticamente para Ollama para voce continuar jogando.*\n\n"
                    + fallback_response
                )

        return _friendly_provider_error(exc, provider)


def narrate_combat(combat_log_text: str) -> str:
    provider, model, base_url, api_key = _provider_config()
    start_time = time.perf_counter()
    prompt_chars = 0
    system = ""
    messages: list[dict] = []
    try:
        err = _check_llm_connection()
        if err:
            return ""

        system = build_combat_narration_system()
        user_msg = build_combat_narration_user(combat_log_text)
        messages = [{"role": "user", "content": user_msg}]
        prompt_chars = len(system) + len(user_msg)

        narration = chat_completion(
            provider=provider,
            model=model,
            system_prompt=system,
            messages=messages,
            temperature=st.session_state.temperature,
            max_tokens=300,
            base_url=base_url,
            api_key=api_key,
            retries=1,
        )
        elapsed = time.perf_counter() - start_time
        _record_llm_metric(
            call_type="combat",
            elapsed_s=elapsed,
            success=True,
            prompt_chars=prompt_chars,
            response_chars=len(narration),
            provider_override=provider,
            model_override=model,
        )
        return narration
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        raw_error = str(exc)
        _record_llm_metric(
            call_type="combat",
            elapsed_s=elapsed,
            success=False,
            prompt_chars=prompt_chars,
            response_chars=0,
            error=raw_error,
            provider_override=provider,
            model_override=model,
        )

        if provider == "gemini" and _is_quota_error(raw_error):
            alt_start = time.perf_counter()
            alt_result = _try_gemini_alternate_model(system_prompt=system, messages=messages, max_tokens=300)
            if alt_result:
                alt_model, alt_response = alt_result
                alt_elapsed = time.perf_counter() - alt_start
                _record_llm_metric(
                    call_type="combat_alt_model",
                    elapsed_s=alt_elapsed,
                    success=True,
                    prompt_chars=prompt_chars,
                    response_chars=len(alt_response),
                    provider_override="gemini",
                    model_override=alt_model,
                )
                return alt_response

            fallback_start = time.perf_counter()
            fallback_response = _try_ollama_fallback(system_prompt=system, messages=messages, max_tokens=300)
            if fallback_response:
                fallback_elapsed = time.perf_counter() - fallback_start
                _record_llm_metric(
                    call_type="combat_fallback",
                    elapsed_s=fallback_elapsed,
                    success=True,
                    prompt_chars=prompt_chars,
                    response_chars=len(fallback_response),
                    provider_override="ollama",
                    model_override=st.session_state.ollama_model,
                )
                return fallback_response

        return "*Narracao de combate indisponivel nesta rodada.*"


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():
    with st.sidebar:
        st.title("AI Dungeon Master")
        st.caption("D&D Solo com Inteligencia Artificial")
        st.divider()

        in_game = st.session_state.game_phase in ["playing", "combat"]

        if not in_game:
            # Config completa antes de jogar
            with st.expander("Configuracao da IA", expanded=(st.session_state.game_phase == "setup")):
                provider = st.selectbox(
                    "Provedor",
                    ["ollama", "gemini"],
                    index=0 if st.session_state.llm_provider == "ollama" else 1,
                    format_func=lambda x: "Ollama (local/gratis)" if x == "ollama" else "Gemini Flash (API gratis)",
                )
                st.session_state.llm_provider = provider

                if provider == "ollama":
                    st.session_state.ollama_url = st.text_input(
                        "Ollama URL",
                        value=st.session_state.ollama_url,
                    )
                    st.session_state.ollama_model = st.text_input(
                        "Modelo Ollama",
                        value=st.session_state.ollama_model,
                        help="Ex: llama3.1, mistral, gemma2",
                    )
                else:
                    st.session_state.gemini_model = st.text_input(
                        "Modelo Gemini",
                        value=st.session_state.gemini_model,
                        help="Ex: gemini-2.5-flash-lite, gemini-2.5-flash",
                    )
                    st.session_state.gemini_api_key = st.text_input(
                        "Gemini API Key",
                        value=st.session_state.gemini_api_key,
                        type="password",
                        help="Crie em https://aistudio.google.com/app/apikey",
                    )
                    st.session_state.gemini_api_key = _normalize_api_key(st.session_state.gemini_api_key)

                temp = st.slider(
                    "Temperatura",
                    min_value=0.1, max_value=1.5, step=0.1,
                    value=st.session_state.temperature,
                    help="Menor = mais previsivel. Maior = mais criativo."
                )
                st.session_state.temperature = temp

                if st.button("Testar conexao", use_container_width=True):
                    err = _check_llm_connection()
                    if err:
                        st.error(err)
                    else:
                        run_err = _check_generation_capability()
                        if run_err:
                            st.error(run_err)
                        else:
                            st.success("Conexao e geracao OK!")

            with st.expander("Modelo de Mestre", expanded=(st.session_state.game_phase == "setup")):
                for key, style in MASTER_STYLES.items():
                    is_selected = st.session_state.master_style == key
                    if st.button(
                        f"{style['name']} {'(ativo)' if is_selected else ''}",
                        use_container_width=True,
                        key=f"style_{key}",
                    ):
                        st.session_state.master_style = key
                        st.rerun()
                    st.caption(style["description"])

        # Character sheet (compacto durante o jogo)
        if st.session_state.character:
            char = st.session_state.character

            if in_game:
                # --- SIDEBAR COMPACTA DURANTE O JOGO ---
                st.markdown(f"**{char.name}** -- {char.race.value} {char.char_class.value} Nv.{char.level}")

                hp_pct = char.hp / char.max_hp
                hp_color = "critico" if hp_pct <= 0.25 else ("baixo" if hp_pct <= 0.5 else "")
                hp_suffix = f" [{hp_color}]" if hp_color else ""
                st.markdown(f"HP{hp_suffix}: **{char.hp}/{char.max_hp}** | CA: **{char.ac}**")
                st.progress(hp_pct)

                st.markdown(f"Ouro: **{char.gold}** | XP: **{char.xp}** | Nv: **{char.level}**")

                cls_data = CLASS_DATA[char.char_class]
                special_name = cls_data["special"].split("**")[1] if "**" in cls_data["special"] else "Especial"
                st.markdown(f"{special_name}: **{char.special_uses}/{char.max_special_uses}**")

                room = st.session_state.current_room
                total = st.session_state.total_rooms
                st.progress(room / total, text=f"Sala {room}/{total}")

                if char.keys:
                    st.markdown("**Chaves:** " + ", ".join(char.keys))

            else:
                # --- SIDEBAR COMPLETA (setup/character creation) ---
                st.divider()
                st.subheader(char.name)
                st.caption(f"{char.race.value} {char.char_class.value} -- Nv. {char.level}")

                hp_pct = char.hp / char.max_hp
                st.markdown(f"**HP: {char.hp}/{char.max_hp}**")
                st.progress(hp_pct)

                col_a, col_b = st.columns(2)
                col_a.metric("CA", char.ac)
                col_b.metric("Ouro", char.gold)

                col_c, col_d = st.columns(2)
                col_c.metric("XP", char.xp)
                col_d.metric("Nivel", char.level)

                with st.expander("Atributos"):
                    cols = st.columns(3)
                    for i, ab in enumerate(["FOR", "DES", "CON", "INT", "SAB", "CAR"]):
                        val = char.abilities[ab]
                        mod = ability_modifier(val)
                        mod_str = f"+{mod}" if mod >= 0 else str(mod)
                        cols[i % 3].metric(ab, val, mod_str)

                cls_data = CLASS_DATA[char.char_class]
                with st.expander("Habilidade Especial"):
                    st.markdown(cls_data["special"])
                    st.markdown(f"Usos: **{char.special_uses}/{char.max_special_uses}**")

                with st.expander("Inventario"):
                    for item in char.inventory:
                        st.markdown(f"- {item}")
                    if char.keys:
                        st.markdown("**Chaves:**")
                        for k in char.keys:
                            st.markdown(f"- {k}")

        with st.expander("Metricas de IA"):
            metrics = st.session_state.llm_metrics
            if not metrics:
                st.caption("Sem dados ainda. Jogue algumas rodadas para gerar metricas.")
            else:
                success_count = sum(1 for m in metrics if m.get("success"))
                failed_count = len(metrics) - success_count
                latencies = [m.get("elapsed_s", 0) for m in metrics if m.get("success")]
                if latencies:
                    st.metric("Latencia media", f"{sum(latencies) / len(latencies):.2f}s")
                st.caption(f"Chamadas: {len(metrics)} | Sucesso: {success_count} | Falhas: {failed_count}")

                csv_data = _metrics_csv()
                st.download_button(
                    "Exportar metricas CSV",
                    data=csv_data,
                    file_name="llm_metrics.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        col_save, col_load = st.columns(2)
        if col_save.button("Salvar Jogo", use_container_width=True):
            ok, msg = save_game_state()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        if col_load.button("Carregar Jogo", use_container_width=True):
            ok, msg = load_game_state()
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

        st.divider()
        if st.button("Novo Jogo", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            init_session_state()
            st.rerun()


# ============================================================
# TELA: SETUP
# ============================================================

def render_setup():
    st.title("AI Dungeon Master")
    st.markdown("##### Aventura Solo de D&D com Inteligencia Artificial")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Como Funciona")
        st.markdown("""
        1. **Configure a IA** na barra lateral (Ollama ou Gemini)
        2. **Escolha o modelo de mestre** (Narrativo, Tatico ou Classico)
        3. **Crie seu personagem** escolhendo raca e classe
        4. **Explore a dungeon** -- a IA narra a aventura
        5. **Sobreviva ate o boss final!**
        """)

    with col2:
        st.markdown("#### Classes Disponiveis")
        for cls in CharClass:
            data = CLASS_DATA[cls]
            st.markdown(f"**{cls.value}** -- {data['description']}")

    st.markdown("---")

    err = _check_llm_connection()
    if err:
        st.warning("A IA nao esta conectada. Configure o provedor na barra lateral e clique em 'Testar conexao'.")
    else:
        if st.button("Criar Personagem e Comecar", type="primary", use_container_width=True):
            st.session_state.game_phase = "character_creation"
            st.rerun()


# ============================================================
# TELA: CRIACAO DE PERSONAGEM
# ============================================================

def render_character_creation():
    st.title("Criacao de Personagem")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        name = st.text_input("Nome do Personagem", value="Thorin", max_chars=30)

        race = st.selectbox(
            "Raca",
            [r for r in Race],
            format_func=lambda r: f"{r.value} -- {RACE_DATA[r]['trait'][:50]}...",
        )

        char_class = st.selectbox(
            "Classe",
            [c for c in CharClass],
            format_func=lambda c: f"{c.value} -- {CLASS_DATA[c]['description'][:50]}...",
        )

    with col2:
        st.markdown("### Preview")
        st.markdown(f"**{name}** -- {race.value} {char_class.value}")
        st.markdown(f"\n**Raca:** {RACE_DATA[race]['trait']}")
        st.markdown(f"\n**Classe:** {CLASS_DATA[char_class]['description']}")
        st.markdown(f"\n**Habilidade:** {CLASS_DATA[char_class]['special']}")
        st.markdown(f"\n**HP Base:** {CLASS_DATA[char_class]['hp_base']} | **Dado de Vida:** {CLASS_DATA[char_class]['hit_die']}")

    st.markdown("---")

    st.markdown("### Configuracao da Dungeon")
    col3, col4 = st.columns(2)

    with col3:
        total_rooms = st.select_slider(
            "Numero de salas",
            options=[5, 7, 10],
            value=7,
            help="5 = curta (~30min), 7 = media (~1h), 10 = longa (~1.5h)"
        )

    with col4:
        theme_idx = st.selectbox(
            "Tema da Dungeon",
            range(len(DUNGEON_THEMES)),
            format_func=lambda i: DUNGEON_THEMES[i][:60] + "...",
        )

    st.markdown("---")

    if st.button("Criar Personagem e Entrar na Dungeon", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Digite um nome para o personagem!")
            return

        char = Character(name=name.strip(), race=race, char_class=char_class)
        st.session_state.character = char
        st.session_state.total_rooms = total_rooms
        room_seq = get_room_sequence(total_rooms)
        st.session_state.room_sequence = room_seq
        st.session_state.dungeon_theme = DUNGEON_THEMES[theme_idx]
        st.session_state.current_room = 1

        # Gera mapa da dungeon com bloqueios
        num_locks = 1 if total_rooms <= 5 else (2 if total_rooms <= 7 else 3)
        dmap = generate_dungeon_map(room_seq, num_locks=num_locks)
        dmap.rooms[0].explored = True
        st.session_state.dungeon_map = dmap

        st.session_state.game_phase = "playing"

        with st.spinner("O Mestre esta preparando a aventura..."):
            room_name = dmap.rooms[0].name
            response = get_ai_response(
                f"Entro na dungeon. O tema e: {st.session_state.dungeon_theme}. "
                f"A primeira sala se chama '{room_name}' e e do tipo {room_seq[0]}. Descreva-a.",
                system_override=build_system_prompt(
                    char, 1, total_rooms,
                    master_style=st.session_state.master_style,
                    locks=dmap.locks,
                ),
            )

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


# ============================================================
# MAPA DA DUNGEON (tela cheia)
# ============================================================

@st.dialog("Mapa da Dungeon", width="large")
def _show_map_dialog(dmap):
    svg = render_map_svg(dmap)
    st.markdown(svg, unsafe_allow_html=True)

    lock_text = get_lock_status_text(dmap)
    if lock_text:
        st.markdown("---")
        st.markdown(lock_text)

    # Legenda por tipo
    st.markdown("---")
    st.markdown("**Tipos:** ? Exploracao | X Combate | $ Tesouro | + Descanso | !! Boss | # Trancada")

    if st.button("Fechar", use_container_width=True):
        st.session_state.show_map = False
        st.rerun()


# ============================================================
# TELA: JOGANDO (Exploracao)
# ============================================================

def render_playing():
    char = st.session_state.character
    dmap = st.session_state.dungeon_map

    # --- Dialog do mapa (tela cheia) ---
    if st.session_state.get("show_map") and st.session_state.has_map and dmap:
        _show_map_dialog(dmap)

    room = st.session_state.current_room
    total = st.session_state.total_rooms
    room_name = ""
    if dmap:
        droom = dmap.get_room(room)
        if droom:
            room_name = f" -- {droom.name}"
    st.markdown(f"### Sala {room} de {total}{room_name}")

    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            role = msg["role"]
            if role == "assistant":
                with st.chat_message("assistant", avatar=None):
                    st.markdown(msg["content"])
            elif role == "user":
                with st.chat_message("user", avatar=None):
                    st.markdown(msg["content"])
            elif role == "system":
                with st.chat_message("assistant", avatar=None):
                    st.markdown(msg["content"])

    st.markdown("---")

    if st.session_state.game_phase == "combat":
        render_combat()
        return

    col_input, col_actions = st.columns([3, 1])

    with col_actions:
        st.markdown("**Painel de Acoes**")

        st.caption("Navegacao")
        if st.button("Proxima Sala", type="primary", use_container_width=True):
            advance_room()

        if st.session_state.has_map and st.button("Ver Mapa", use_container_width=True):
            st.session_state.show_map = True
            st.rerun()

        st.caption("Recursos")
        r1, r2 = st.columns(2)
        with r1:
            if st.button("Pocao", use_container_width=True):
                result = use_potion(char)
                st.session_state.messages.append({"role": "system", "content": result})
                st.rerun()
        with r2:
            if st.button("Descanso", use_container_width=True):
                result = char.short_rest()
                st.session_state.messages.append({"role": "system", "content": result})
                st.rerun()

        st.caption("Utilitarios")
        if st.button("Ver Ficha", use_container_width=True):
            st.session_state.messages.append({"role": "system", "content": char.character_sheet()})
            st.rerun()

    with col_input:
        user_input = st.chat_input("O que voce faz? (descreva sua acao)")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner("O Mestre pondera..."):
            response = get_ai_response(user_input)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


def advance_room():
    char = st.session_state.character
    current = st.session_state.current_room
    total = st.session_state.total_rooms
    dmap = st.session_state.dungeon_map

    if current >= total:
        st.session_state.game_phase = "game_over"
        victory_msg = f"""
# VITORIA!

**{char.name}** sobreviveu a dungeon!

### Estatisticas Finais
- Salas exploradas: {total}
- XP total: {char.xp}
- Ouro: {char.gold}
- HP final: {char.hp}/{char.max_hp}
- Nivel final: {char.level}

*Parabens, aventureiro! A dungeon foi conquistada!*
"""
        st.session_state.messages.append({"role": "assistant", "content": victory_msg})
        st.rerun()
        return

    next_room_num = current + 1
    next_droom = dmap.get_room(next_room_num) if dmap else None

    # Verificar bloqueio
    if next_droom and next_droom.locked:
        lock = next_droom.lock_info
        key_name = lock.get("key_name", "")
        # Verifica se o jogador tem a chave
        lock_data = next((l for l in dmap.locks if l["lock_room"] == next_room_num), None)
        if lock_data and not lock_data["unlocked"]:
            if char.has_key(key_name):
                lock_data["unlocked"] = True
                next_droom.locked = False
                st.session_state.messages.append({
                    "role": "system",
                    "content": f"Voce usa **{key_name}** para desbloquear a passagem! {lock['description']}"
                })
            else:
                st.session_state.messages.append({
                    "role": "system",
                    "content": f"**Passagem bloqueada!** {lock['description']}\nVoce precisa de: *{key_name}*.\n\nExplore outras salas para encontrar o item necessario."
                })
                st.rerun()
                return

    st.session_state.current_room = next_room_num
    room_idx = next_room_num - 1
    room_type = st.session_state.room_sequence[room_idx] if room_idx < len(st.session_state.room_sequence) else "exploration"

    # Atualiza mapa
    if dmap:
        dmap.current_room = next_room_num
        dr = dmap.get_room(next_room_num)
        if dr:
            dr.explored = True

    if room_type in ["combat", "boss"]:
        start_combat(is_boss=(room_type == "boss"))
        return

    room_name = next_droom.name if next_droom else f"Sala {next_room_num}"

    # Verificar se a sala contem uma chave
    key_in_room = ""
    if next_droom and next_droom.has_key:
        key_in_room = next_droom.has_key

    extra = ""
    if room_type == "rest":
        extra = "Sala segura. O personagem pode descansar e recuperar HP."
    elif room_type == "treasure":
        extra = "Sala de tesouro! Descreva loot interessante (itens, ouro, pocoes)."
    if key_in_room:
        extra += f"\nNesta sala ha um item-chave escondido: '{key_in_room}'. Descreva-o como parte do ambiente."

    with st.spinner("O Mestre prepara a proxima sala..."):
        msg = f"Avanco para a sala {next_room_num}, chamada '{room_name}'. (Tipo: {room_type}). Descreva esta nova sala."
        if extra:
            msg += f" {extra}"
        response = get_ai_response(msg)

    st.session_state.messages.append({"role": "user", "content": f"*Avanca para {room_name}...*"})
    st.session_state.messages.append({"role": "assistant", "content": response})

    # Dar chave automaticamente se a sala tem uma
    if key_in_room:
        char.add_key(key_in_room)
        lock_info = next((l for l in dmap.locks if l["key_name"] == key_in_room), None)
        key_desc = lock_info["key_description"] if lock_info else key_in_room
        st.session_state.messages.append({
            "role": "system",
            "content": f"Voce encontrou: **{key_in_room}** -- *{key_desc}*"
        })

    if room_type == "treasure":
        gold = SYSTEM_RNG.randint(10, 50) * char.level
        char.gold += gold
        potion_chance = SYSTEM_RNG.random()
        loot_msg = f"Encontrou **{gold} pecas de ouro**!"
        if potion_chance > 0.5:
            char.inventory.append("Pocao de Cura")
            loot_msg += "\nEncontrou uma **Pocao de Cura**!"
        st.session_state.messages.append({"role": "system", "content": loot_msg})

    # Chance de encontrar o mapa da dungeon em salas de exploracao/tesouro
    if not st.session_state.has_map and room_type in ["exploration", "treasure"]:
        if SYSTEM_RNG.random() < 0.5 or next_room_num >= total // 2:
            st.session_state.has_map = True
            st.session_state.messages.append({
                "role": "system",
                "content": (
                    "Voce encontra um **Mapa da Dungeon** enrolado em um canudo de couro! "
                    "Agora pode consultar o mapa usando o botao 'Ver Mapa' nas acoes rapidas."
                )
            })

    st.rerun()


# ============================================================
# TELA: COMBATE
# ============================================================

def start_combat(is_boss: bool = False):
    char = st.session_state.character
    dmap = st.session_state.dungeon_map

    # Marca sala como explorada no mapa
    if dmap:
        dmap.current_room = st.session_state.current_room
        dr = dmap.get_room(st.session_state.current_room)
        if dr:
            dr.explored = True

    # Verificar se a sala de combate tem chave
    key_in_room = ""
    if dmap:
        dr = dmap.get_room(st.session_state.current_room)
        if dr and dr.has_key:
            key_in_room = dr.has_key

    if is_boss:
        boss_options = ["troll", "dragao_jovem", "aranha_gigante"]
        boss_key = SYSTEM_RNG.choice(boss_options)
        monsters = [MONSTER_TEMPLATES[boss_key]()]
        monsters[0].name = f"{monsters[0].name} [BOSS]"
        monsters[0].hp = int(monsters[0].hp * 1.5)
        monsters[0].max_hp = monsters[0].hp
    else:
        monsters = get_encounter_for_level(char.level)

    st.session_state.combat_monsters = monsters
    st.session_state.combat_turn = "player"
    st.session_state.combat_log = []
    st.session_state.game_phase = "combat"
    st.session_state["combat_key_reward"] = key_in_room

    monster_names = ", ".join(m.name for m in monsters)
    combat_intro = f"""
## COMBATE

Inimigos: **{monster_names}**

"""
    for m in monsters:
        combat_intro += f"- **{m.name}** -- HP: {m.hp}/{m.max_hp} | CA: {m.ac}\n"
        if m.description:
            combat_intro += f"  *{m.description}*\n"
        if m.special:
            combat_intro += f"  _{m.special}_\n"

    combat_intro += "\n**Seu turno! Escolha uma acao abaixo.**"

    st.session_state.messages.append({"role": "system", "content": combat_intro})

    with st.spinner("O Mestre narra o encontro..."):
        narration = get_ai_response(
            f"Encontro {monster_names} na sala {st.session_state.current_room}! Descreva o inicio do combate dramaticamente."
        )
    st.session_state.messages.append({"role": "assistant", "content": narration})

    st.rerun()


def render_combat():
    char = st.session_state.character
    monsters = st.session_state.combat_monsters
    alive_monsters = [m for m in monsters if m.is_alive()]

    if not alive_monsters:
        end_combat_victory()
        return

    if not char.is_alive():
        end_combat_defeat()
        return

    st.markdown("### Inimigos")
    for m in monsters:
        if m.is_alive():
            hp_pct = m.hp / m.max_hp
            col1, col2 = st.columns([2, 3])
            with col1:
                st.markdown(f"**{m.name}** -- CA: {m.ac}")
            with col2:
                st.progress(hp_pct, text=f"HP: {m.hp}/{m.max_hp}")
        else:
            st.markdown(f"~~{m.name}~~ -- Derrotado")

    st.markdown("---")

    if st.session_state.combat_turn == "player":
        st.markdown("### Seu Turno")
        target_idx = 0
        if len(alive_monsters) > 1:
            target_idx = st.selectbox(
                "Escolha o alvo:",
                range(len(alive_monsters)),
                format_func=lambda i: f"{alive_monsters[i].name} (HP: {alive_monsters[i].hp}/{alive_monsters[i].max_hp})"
            )

        special_label = CLASS_DATA[char.char_class]["special"].split("**")[1] if "**" in CLASS_DATA[char.char_class]["special"] else "Especial"
        can_use = char.special_uses > 0

        st.caption("Acoes ofensivas")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Atacar", type="primary", use_container_width=True):
                execute_player_turn(alive_monsters[target_idx], use_special=False)

        with col2:
            if st.button(
                f"{special_label} ({char.special_uses})",
                use_container_width=True,
                disabled=not can_use
            ):
                execute_player_turn(alive_monsters[target_idx], use_special=True)

        st.caption("Acoes defensivas")
        col3, col4 = st.columns(2)

        with col3:
            if st.button("Pocao", use_container_width=True):
                result = use_potion(char)
                st.session_state.messages.append({"role": "system", "content": result})
                execute_monster_turns()

        with col4:
            if st.button("Fugir", use_container_width=True):
                check = roll_check(char.mod("DES"), 12)
                if check["success"]:
                    st.session_state.messages.append({
                        "role": "system",
                        "content": f"**Fuga bem-sucedida!** {check['description']}"
                    })
                    st.session_state.game_phase = "playing"
                    st.session_state.combat_monsters = []
                else:
                    st.session_state.messages.append({
                        "role": "system",
                        "content": f"**Fuga falhou!** {check['description']}\nOs monstros atacam!"
                    })
                    execute_monster_turns()
                st.rerun()


def execute_player_turn(target: Monster, use_special: bool):
    char = st.session_state.character
    result = resolve_player_attack(char, target, use_special)
    st.session_state.messages.append({"role": "system", "content": f"**Seu ataque:**\n{result}"})
    st.session_state.combat_log.append(result)

    alive = [m for m in st.session_state.combat_monsters if m.is_alive()]
    if not alive:
        end_combat_victory()
        return

    execute_monster_turns()


def execute_monster_turns():
    char = st.session_state.character
    monsters = st.session_state.combat_monsters

    for m in monsters:
        if m.is_alive() and char.is_alive():
            result = resolve_monster_attack(m, char)
            st.session_state.messages.append({"role": "system", "content": result})
            st.session_state.combat_log.append(result)

    if not char.is_alive():
        end_combat_defeat()
        return

    st.rerun()


def end_combat_victory():
    char = st.session_state.character
    dmap = st.session_state.dungeon_map
    total_xp = sum(m.xp_reward for m in st.session_state.combat_monsters)
    gold = SYSTEM_RNG.randint(5, 20) * char.level

    xp_msg = char.gain_xp(total_xp)
    char.gold += gold

    victory_msg = f"""
## Vitoria!

{xp_msg}
Saqueou **{gold}** pecas de ouro!
HP: **{char.hp}/{char.max_hp}**
"""
    st.session_state.messages.append({"role": "system", "content": victory_msg})

    # Dar chave se esta sala de combate tinha uma
    key_reward = st.session_state.get("combat_key_reward", "")
    if key_reward and dmap:
        char.add_key(key_reward)
        lock_info = next((l for l in dmap.locks if l["key_name"] == key_reward), None)
        key_desc = lock_info["key_description"] if lock_info else key_reward
        st.session_state.messages.append({
            "role": "system",
            "content": f"Ao derrotar os inimigos, voce encontra: **{key_reward}** -- *{key_desc}*"
        })

    monster_names = ", ".join(m.name for m in st.session_state.combat_monsters)
    with st.spinner("O Mestre narra a vitoria..."):
        narration = narrate_combat(
            f"O jogador {char.name} ({char.char_class.value}) derrotou {monster_names}! "
            f"HP restante: {char.hp}/{char.max_hp}. Narre a vitoria."
        )
    if narration:
        st.session_state.messages.append({"role": "assistant", "content": narration})

    st.session_state.game_phase = "playing"
    st.session_state.combat_monsters = []
    st.session_state.combat_log = []
    st.session_state["combat_key_reward"] = ""
    st.rerun()


def end_combat_defeat():
    char = st.session_state.character
    defeat_msg = f"""
## Derrota...

**{char.name}** caiu em combate na sala {st.session_state.current_room}.

### Estatisticas
- Salas exploradas: {st.session_state.current_room}
- XP total: {char.xp}
- Ouro: {char.gold}

*O dungeon reclama mais uma alma...*
"""
    st.session_state.messages.append({"role": "system", "content": defeat_msg})
    st.session_state.game_phase = "game_over"
    st.rerun()


# ============================================================
# TELA: GAME OVER
# ============================================================

def render_game_over():
    for msg in st.session_state.messages:
        role = msg["role"]
        if role == "assistant":
            with st.chat_message("assistant", avatar=None):
                st.markdown(msg["content"])
        elif role == "user":
            with st.chat_message("user", avatar=None):
                st.markdown(msg["content"])
        elif role == "system":
            with st.chat_message("assistant", avatar=None):
                st.markdown(msg["content"])

    st.markdown("---")
    if st.button("Jogar Novamente", type="primary", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        init_session_state()
        st.rerun()


# ============================================================
# MAIN
# ============================================================

def main():
    render_sidebar()

    phase = st.session_state.game_phase
    if phase == "setup":
        render_setup()
    elif phase == "character_creation":
        render_character_creation()
    elif phase in ["playing", "combat"]:
        render_playing()
    elif phase == "game_over":
        render_game_over()


if __name__ == "__main__":
    main()
