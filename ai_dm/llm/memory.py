"""Memoria narrativa com stream, reflexoes e retrieval leve.

Inspirado em Generative Agents (Park et al., 2023):
- memory stream: eventos pontuais ordenados por turno
- reflection: consolidacoes de alto nivel
- retrieval: combinacao de recencia, importancia e relevancia lexical

Mantem compatibilidade com o WorldState legado (npcs/facts/decisoes).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


_TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9]{3,}")


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text or "")}


def _clip_text(text: str, max_chars: int = 240) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def estimate_importance(text: str, kind: str = "fact") -> float:
    """Heuristica barata para priorizar eventos persistentes.

    A escala e [0.0, 1.0]. Eventos envolvendo chefes, chaves, bloqueios,
    NPCs e decisoes do jogador recebem peso maior.
    """
    lowered = (text or "").lower()
    score = 0.35
    if kind == "reflection":
        return 0.95
    if kind == "decision":
        score += 0.12
    if kind == "npc":
        score += 0.1
    keywords = (
        "boss", "chefe", "drag", "chave", "tranc", "porta", "artefato",
        "mapa", "segredo", "tesouro", "prision", "pacto", "altar",
        "necromante", "portal", "jurou", "decidiu", "alianca",
    )
    hits = sum(1 for keyword in keywords if keyword in lowered)
    score += min(hits * 0.1, 0.4)
    if "!" in lowered:
        score += 0.05
    return max(0.05, min(score, 1.0))


@dataclass
class MemoryEntry:
    text: str
    kind: str = "fact"
    importance: float = 0.5
    turn: int = 0
    source: str = ""
    tags: list[str] = field(default_factory=list)
    access_count: int = 0
    last_access_turn: int = 0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "kind": self.kind,
            "importance": self.importance,
            "turn": self.turn,
            "source": self.source,
            "tags": list(self.tags),
            "access_count": self.access_count,
            "last_access_turn": self.last_access_turn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(
            text=str(data.get("text", "")),
            kind=str(data.get("kind", "fact")),
            importance=float(data.get("importance", 0.5)),
            turn=int(data.get("turn", 0)),
            source=str(data.get("source", "")),
            tags=list(data.get("tags", [])),
            access_count=int(data.get("access_count", 0)),
            last_access_turn=int(data.get("last_access_turn", 0)),
        )


@dataclass
class RetrievedMemory:
    entry: MemoryEntry
    score: float
    relevance: float
    recency: float


@dataclass
class MemoryStream:
    entries: list[MemoryEntry] = field(default_factory=list)
    next_turn: int = 1
    last_reflection_turn: int = 0
    reflection_interval: int = 6
    reflection_window: int = 8
    max_reflections: int = 6

    def to_dict(self) -> dict:
        legacy = self.legacy_snapshot()
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "next_turn": self.next_turn,
            "last_reflection_turn": self.last_reflection_turn,
            "reflection_interval": self.reflection_interval,
            "reflection_window": self.reflection_window,
            "max_reflections": self.max_reflections,
            **legacy,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "MemoryStream":
        if not data:
            return cls()
        if data.get("entries"):
            entries = [MemoryEntry.from_dict(item) for item in data.get("entries", [])]
            next_turn = int(data.get("next_turn", (max((entry.turn for entry in entries), default=0) + 1)))
            return cls(
                entries=entries,
                next_turn=next_turn,
                last_reflection_turn=int(data.get("last_reflection_turn", 0)),
                reflection_interval=int(data.get("reflection_interval", 6)),
                reflection_window=int(data.get("reflection_window", 8)),
                max_reflections=int(data.get("max_reflections", 6)),
            )
        return cls.from_legacy_world_state(data)

    @classmethod
    def from_legacy_world_state(cls, data: dict | None) -> "MemoryStream":
        stream = cls()
        if not data:
            return stream
        for name in data.get("npcs", []):
            stream.remember(name, kind="npc", importance=0.8, source="legacy", auto_reflect=False)
        for fact in data.get("facts", []):
            stream.remember(fact, kind="fact", importance=0.65, source="legacy", auto_reflect=False)
        for decisao in data.get("decisoes", []):
            stream.remember(decisao, kind="decision", importance=0.7, source="legacy", auto_reflect=False)
        stream.maybe_reflect(force=True)
        return stream

    def legacy_snapshot(self) -> dict:
        npcs = [entry.text for entry in self.entries if entry.kind == "npc"][-30:]
        facts = [entry.text for entry in self.entries if entry.kind == "fact"][-50:]
        decisoes = [entry.text for entry in self.entries if entry.kind == "decision"][-30:]
        return {"npcs": npcs, "facts": facts, "decisoes": decisoes}

    def remember(
        self,
        text: str,
        kind: str = "fact",
        importance: float | None = None,
        source: str = "",
        tags: list[str] | None = None,
        turn: int | None = None,
        auto_reflect: bool = True,
    ) -> MemoryEntry | None:
        normalized = _clip_text(text)
        if not normalized:
            return None

        if self.entries and self.entries[-1].text == normalized and self.entries[-1].kind == kind:
            return self.entries[-1]

        entry_turn = self.next_turn if turn is None else int(turn)
        entry = MemoryEntry(
            text=normalized,
            kind=kind,
            importance=estimate_importance(normalized, kind) if importance is None else float(importance),
            turn=entry_turn,
            source=source,
            tags=list(tags or []),
        )
        self.entries.append(entry)
        self.next_turn = max(self.next_turn, entry_turn + 1)

        if auto_reflect and kind != "reflection":
            self.maybe_reflect()
        return entry

    def remember_reflection(self, text: str, source: str = "summary", importance: float = 0.95) -> MemoryEntry | None:
        if any(entry.kind == "reflection" and entry.text == _clip_text(text) for entry in self.entries):
            return None
        reflection = self.remember(
            text,
            kind="reflection",
            importance=importance,
            source=source,
            auto_reflect=False,
        )
        reflections = [entry for entry in self.entries if entry.kind == "reflection"]
        if len(reflections) > self.max_reflections:
            cutoff = len(reflections) - self.max_reflections
            removed = 0
            kept_entries = []
            for entry in self.entries:
                if entry.kind == "reflection" and removed < cutoff:
                    removed += 1
                    continue
                kept_entries.append(entry)
            self.entries = kept_entries
        return reflection

    def maybe_reflect(self, force: bool = False) -> list[MemoryEntry]:
        episodic = [entry for entry in self.entries if entry.kind != "reflection"]
        if not episodic:
            return []

        latest_turn = episodic[-1].turn
        if not force and (latest_turn - self.last_reflection_turn) < self.reflection_interval:
            return []

        recent = episodic[-self.reflection_window :]
        reflections: list[str] = []

        recent_decisions = [entry.text for entry in recent if entry.kind == "decision"][-3:]
        if len(recent_decisions) >= 2:
            reflections.append(
                "Padrao recente do jogador: " + " | ".join(dict.fromkeys(recent_decisions))
            )

        recent_npcs = [entry.text for entry in recent if entry.kind == "npc"][-3:]
        if recent_npcs:
            reflections.append(
                "NPCs que merecem continuidade: " + ", ".join(dict.fromkeys(recent_npcs))
            )

        salient_facts = [entry.text for entry in recent if entry.kind == "fact"]
        if salient_facts:
            top_facts = salient_facts[-2:]
            reflections.append("Fatos consolidados: " + " | ".join(dict.fromkeys(top_facts)))

        created: list[MemoryEntry] = []
        for reflection_text in reflections[:2]:
            reflection = self.remember_reflection(reflection_text, source="auto-reflection", importance=0.88)
            if reflection:
                created.append(reflection)

        self.last_reflection_turn = latest_turn
        return created

    def retrieve(self, query: str = "", limit: int = 6, current_turn: int | None = None) -> list[RetrievedMemory]:
        if not self.entries:
            return []

        effective_turn = current_turn or max((entry.turn for entry in self.entries), default=0)
        query_tokens = _tokenize(query)
        scored: list[RetrievedMemory] = []
        for entry in self.entries:
            entry_tokens = _tokenize(entry.text + " " + " ".join(entry.tags))
            overlap = len(query_tokens & entry_tokens)
            relevance = 0.0
            if query_tokens:
                relevance = overlap / max(len(query_tokens), 1)
            age = max(effective_turn - entry.turn, 0)
            recency = 1 / (1 + math.log1p(age + 1))
            importance = max(0.0, min(entry.importance, 1.0))
            score = (0.45 * importance) + (0.35 * relevance) + (0.20 * recency)
            if entry.kind == "reflection":
                score += 0.05
            scored.append(RetrievedMemory(entry=entry, score=score, relevance=relevance, recency=recency))

        scored.sort(
            key=lambda item: (
                round(item.score, 6),
                round(item.relevance, 6),
                item.entry.turn,
            ),
            reverse=True,
        )
        selected = scored[:limit]
        for item in selected:
            item.entry.access_count += 1
            item.entry.last_access_turn = effective_turn
        return selected

    def render_for_prompt(
        self,
        query: str = "",
        limit: int = 6,
        reflection_limit: int = 2,
        current_turn: int | None = None,
    ) -> str:
        retrieved = self.retrieve(query=query, limit=limit, current_turn=current_turn)
        if not retrieved:
            return ""

        reflections = [item.entry.text for item in retrieved if item.entry.kind == "reflection"][:reflection_limit]
        episodic = [item.entry.text for item in retrieved if item.entry.kind != "reflection"]
        parts = ["<MEMORIA_DO_MUNDO>"]
        if reflections:
            parts.append("Reflexoes relevantes:")
            for reflection in reflections:
                parts.append(f"- {reflection}")
        if episodic:
            parts.append("Memorias recuperadas para a cena atual:")
            for text in episodic:
                parts.append(f"- {text}")
        parts.append("</MEMORIA_DO_MUNDO>")
        return "\n".join(parts)


@dataclass
class WorldState:
    npcs: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    decisoes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"npcs": list(self.npcs), "facts": list(self.facts), "decisoes": list(self.decisoes)}

    @classmethod
    def from_dict(cls, data: dict | None) -> "WorldState":
        if not data:
            return cls()
        if data.get("entries"):
            legacy = MemoryStream.from_dict(data).legacy_snapshot()
            return cls.from_dict(legacy)
        return cls(
            npcs=list(data.get("npcs", [])),
            facts=list(data.get("facts", [])),
            decisoes=list(data.get("decisoes", [])),
        )

    def as_memory_stream(self) -> MemoryStream:
        return MemoryStream.from_legacy_world_state(self.to_dict())

    def add_npc(self, name: str, max_entries: int = 30) -> None:
        if name and name not in self.npcs:
            self.npcs.append(name)
            self.npcs = self.npcs[-max_entries:]

    def add_fact(self, fact: str, max_entries: int = 50) -> None:
        if fact and fact not in self.facts:
            self.facts.append(fact)
            self.facts = self.facts[-max_entries:]

    def add_decisao(self, decisao: str, max_entries: int = 30) -> None:
        if decisao:
            self.decisoes.append(decisao)
            self.decisoes = self.decisoes[-max_entries:]
