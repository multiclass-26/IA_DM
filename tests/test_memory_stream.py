"""Testa memory stream, reflection e retrieval contra o metodo legado."""

from ai_dm.llm.memory import MemoryStream, WorldState
from ai_dm.llm.prompts import build_world_state


def test_memory_stream_roundtrip_and_legacy_projection():
    stream = MemoryStream()
    stream.remember("Irmia, a prisioneira elfa, teme o necromante.", kind="npc", importance=0.9)
    stream.remember("A Porta do Cranio exige a Chave de Osso.", kind="fact", importance=0.95)
    stream.remember("Voce prometeu libertar a prisioneira.", kind="decision", importance=0.85)

    restored = MemoryStream.from_dict(stream.to_dict())

    assert len(restored.entries) == len(stream.entries)
    legacy = restored.legacy_snapshot()
    assert "Irmia, a prisioneira elfa, teme o necromante." in legacy["npcs"]
    assert "A Porta do Cranio exige a Chave de Osso." in legacy["facts"]
    assert "Voce prometeu libertar a prisioneira." in legacy["decisoes"]


def test_retrieval_prioritizes_relevance_and_reflection():
    stream = MemoryStream(reflection_interval=3, reflection_window=6)
    stream.remember("Voce investigou poeira antiga perto da entrada.", kind="decision", importance=0.4)
    stream.remember("Irmia, a prisioneira elfa, viu o cultista com a Chave de Osso.", kind="npc", importance=0.95)
    stream.remember("A Porta do Cranio esta trancada e reage a osso runico.", kind="fact", importance=0.9)
    stream.remember("Voce prometeu libertar a prisioneira antes do boss.", kind="decision", importance=0.92)
    stream.remember("Um altar de cobre cobre o salao inundado.", kind="fact", importance=0.35)
    stream.maybe_reflect(force=True)

    retrieved = stream.retrieve(query="Como salvar a prisioneira e abrir a porta do cranio?", limit=4)
    texts = [item.entry.text for item in retrieved]

    assert any("prisioneira" in text.lower() for text in texts)
    assert any("porta do cranio" in text.lower() for text in texts)
    assert any(item.entry.kind == "reflection" for item in retrieved)


def test_build_world_state_uses_retrieval_and_is_more_compact_than_legacy_dump():
    legacy_world = WorldState(
        npcs=["Irmia", "Balthor", "Mercador dos Fungos"],
        facts=[
            "A Porta do Cranio exige a Chave de Osso.",
            "O cultista manco patrulha a ala leste.",
            "O poço central murmura nomes antigos.",
            "O altar de cobre pulsa quando ha sangue.",
            "Um mercador vende ervas secas na sala 2.",
            "O necromante teme fogo sagrado.",
            "A prisioneira elfa conhece um atalho secreto.",
            "A ponte quebrada range sob peso medio.",
            "A estatua cega esconde moedas antigas.",
            "Ha fungos luminescentes perto da saida norte.",
            "O boss carrega um grimorio costurado em pele.",
            "A agua da cisterna remove venenos fracos.",
        ],
        decisoes=[
            "Voce prometeu salvar a prisioneira.",
            "Voce evitou confronto direto com o cultista.",
            "Voce quer abrir a Porta do Cranio antes do boss.",
        ],
    )

    legacy_render = build_world_state(legacy_world.to_dict())
    stream_render = build_world_state(
        legacy_world.as_memory_stream(),
        query="Como abrir a Porta do Cranio e salvar a prisioneira?",
    )

    assert "Porta do Cranio" in stream_render
    assert "prisioneira" in stream_render.lower()
    assert len(stream_render) < len(legacy_render)
    assert "Memorias recuperadas para a cena atual" in stream_render