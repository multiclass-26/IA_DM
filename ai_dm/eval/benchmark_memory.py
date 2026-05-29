"""Benchmark simples: memoria legada vs memory stream.

Uso offline:
    python -m ai_dm.eval.benchmark_memory

Uso com Gemini:
    $env:GEMINI_API_KEY="..."
    python -m ai_dm.eval.benchmark_memory --live
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from dataclasses import asdict, dataclass

from ai_dm.domain.character import CharClass, Character, Race
from ai_dm.llm.client import DEFAULT_GEMINI_BASE_URL, chat_completion
from ai_dm.llm.memory import WorldState
from ai_dm.llm.prompts import build_system_prompt, build_world_state


@dataclass
class BenchmarkSample:
    name: str
    prompt_chars: int
    response_chars: int = 0
    elapsed_s: float = 0.0


def _fixture_world() -> WorldState:
    return WorldState(
        npcs=[
            "Irmia, a prisioneira elfa que conhece um atalho secreto.",
            "Balthor, um cultista manco que patrulha a ala leste.",
            "Mercador dos Fungos, um anao que troca ervas por favores.",
        ],
        facts=[
            "A Porta do Cranio exige a Chave de Osso.",
            "O necromante teme fogo sagrado.",
            "O poço central murmura nomes antigos durante a meia-noite.",
            "O altar de cobre pulsa quando ha sangue no chao.",
            "A ponte quebrada range sob peso medio.",
            "A estatua cega esconde moedas antigas.",
            "Ha fungos luminescentes perto da saida norte.",
            "A agua da cisterna remove venenos fracos.",
            "O boss carrega um grimorio costurado em pele.",
            "A prisioneira elfa teme ser sacrificada ao amanhecer.",
            "Um corredor lateral leva a uma cela esquecida.",
            "O mapa parcial indica uma passagem atras do altar.",
        ],
        decisoes=[
            "Voce prometeu salvar a prisioneira.",
            "Voce evitou confronto direto com o cultista.",
            "Voce quer abrir a Porta do Cranio antes do boss.",
        ],
    )


def _build_samples(query: str) -> tuple[Character, str, str]:
    char = Character(name="Aldren", race=Race.HUMANO, char_class=CharClass.PALADINO)
    world = _fixture_world()
    legacy_render = build_world_state(world.to_dict())
    stream_render = build_world_state(world.as_memory_stream(), query=query)
    return char, legacy_render, stream_render


def offline_benchmark(query: str) -> dict:
    _, legacy_render, stream_render = _build_samples(query)
    return {
        "query": query,
        "legacy_prompt_chars": len(legacy_render),
        "stream_prompt_chars": len(stream_render),
        "saved_chars": len(legacy_render) - len(stream_render),
        "saved_percent": round((1 - (len(stream_render) / max(len(legacy_render), 1))) * 100, 2),
        "legacy_preview": legacy_render,
        "stream_preview": stream_render,
    }


def live_benchmark(query: str, runs: int, model: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Defina GEMINI_API_KEY no ambiente antes de usar --live.")

    char, _, _ = _build_samples(query)
    world = _fixture_world()

    samples: list[BenchmarkSample] = []
    for name, world_state in [
        ("legacy", world.to_dict()),
        ("memory_stream", world.as_memory_stream()),
    ]:
        for _ in range(runs):
            system_prompt = build_system_prompt(
                char,
                room_number=4,
                total_rooms=7,
                master_style="classico",
                locks=None,
                world_state=world_state,
                memory_query=query,
            )
            response = chat_completion(
                provider="gemini",
                model=model,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": query}],
                temperature=0.2,
                max_tokens=220,
                base_url=DEFAULT_GEMINI_BASE_URL,
                api_key=api_key,
                retries=0,
                timeout=60,
            )
            samples.append(
                BenchmarkSample(
                    name=name,
                    prompt_chars=response.prompt_chars,
                    response_chars=response.response_chars,
                    elapsed_s=response.elapsed_s,
                )
            )

    grouped: dict[str, list[BenchmarkSample]] = {"legacy": [], "memory_stream": []}
    for sample in samples:
        grouped[sample.name].append(sample)

    return {
        key: {
            "runs": len(group),
            "avg_prompt_chars": round(statistics.mean(item.prompt_chars for item in group), 2),
            "avg_response_chars": round(statistics.mean(item.response_chars for item in group), 2),
            "avg_elapsed_s": round(statistics.mean(item.elapsed_s for item in group), 3),
            "samples": [asdict(item) for item in group],
        }
        for key, group in grouped.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark da memoria narrativa")
    parser.add_argument(
        "--query",
        default="Como abrir a Porta do Cranio e salvar a prisioneira sem alertar o cultista?",
    )
    parser.add_argument("--live", action="store_true", help="Executa chamadas reais no Gemini.")
    parser.add_argument("--runs", type=int, default=2, help="Numero de execucoes por metodo no modo live.")
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    args = parser.parse_args()

    result = {"offline": offline_benchmark(args.query)}
    if args.live:
        result["live"] = live_benchmark(args.query, args.runs, args.model)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()