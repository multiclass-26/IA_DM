# AI Dungeon Master

Dungeon crawl solo de D&D 5e simplificado com LLM (Gemini ou Ollama) atuando
como **Mestre**.
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"            # instala pacote + ferramentas de teste
copy .env.example .env             # opcional: defina GEMINI_API_KEY
python -m streamlit run app.py
```

## Provedores de LLM

**Gemini Flash (gratuito via AI Studio):**
- Gere chave em https://aistudio.google.com/app/apikey
- Modelo recomendado: `gemini-2.5-flash-lite` (fallback automatico para `gemini-2.5-flash` ao detectar 404)

**Ollama (local):**
- Instale: https://ollama.com
- `ollama pull llama3.1`
- Selecione provedor `ollama` na sidebar

## Estrutura (v1.0)

```
ai_dm/                # pacote principal
  domain/             # regras puras: dice, character, monster, dungeon, events
  engine/             # orquestracao: combat (e session futuramente)
  llm/                # cliente, prompts, guardrails, memoria, metricas
  persistence/        # save/load com SCHEMA_VERSION e migracao
  ui/                 # styles (CSS) - views ainda em app.py
app.py                # entrypoint Streamlit
tests/                # 151 testes pytest cobrindo regras + persistencia
tests/eval/           # cenarios YAML para auditoria manual da LLM
docs/PLANO_V1.md      # planejamento da modernizacao
```

Os modulos legados (`game_engine.py`, `dungeon_map.py`, `prompts.py`,
`llm_client.py`) viraram **shims** que re-exportam o novo pacote -
mantendo o `app.py` funcionando sem mudancas de import.

## Features

- Sistema de D&D 5e simplificado (dados, atributos, CA, HP, salvaguardas)
- 6 classes com habilidades especiais; 6 racas com tracos
- 12 monstros, encontros balanceados por nivel
- Dungeons procedurais (5, 7 ou 10 salas) com chaves/bloqueios coerentes
- Narrativa via LLM com guardrails (sem matematica de combate na narracao)
- Combate deterministico no motor; LLM apenas narra
- Memoria de mundo (NPCs, fatos, decisoes) injetada no prompt
- Progressao de nivel com multiplos level-ups num unico ganho de XP
- Salvar/carregar com migracao de schema; nunca persiste segredos
- Exportacao de metricas de IA (`llm_metrics.csv`)