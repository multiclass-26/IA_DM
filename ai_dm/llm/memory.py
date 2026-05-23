"""WorldState: memória estruturada do mundo (NPCs, fatos, decisões)."""

from __future__ import annotations

from dataclasses import dataclass, field


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
        return cls(
            npcs=list(data.get("npcs", [])),
            facts=list(data.get("facts", [])),
            decisoes=list(data.get("decisoes", [])),
        )

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
