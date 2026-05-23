# AI Dungeon Master — Revisão geral e plano para v1.0

> Documento de planejamento. Não altera código. Reúne (1) auditoria do que existe, (2) dores reais confirmadas por teste, (3) referências externas e (4) roadmap incremental até v1.0.

---

## 1. Estado atual (resumo da auditoria)

| Módulo | Linhas aprox. | Saúde | Comentário |
|---|---|---|---|
| [app.py](../app.py) | ~1500 | **Frágil** | Único arquivo carrega UI + persistência + orquestração LLM + lógica de jogo. Difícil testar. |
| [game_engine.py](../game_engine.py) | ~700 | OK | Mecânicas D&D simplificadas, dataclasses limpos. Bugs pontuais (ver §2). |
| [dungeon_map.py](../dungeon_map.py) | ~280 | OK | SVG inline + geração por grafo. Sem testes. |
| [llm_client.py](../llm_client.py) | ~60 | OK | Wrapper OpenAI-compat. Falta logging estruturado. |
| [prompts.py](../prompts.py) | ~300 | Bom | Já aplica persona anchoring, few-shot, constraints. Pode evoluir para JSON-mode/CoT. |
| Testes | 0 | **Crítico** | Não existem. |
| CI / lint | 0 | **Crítico** | Sem pipeline, sem `ruff`/`mypy`, sem `pytest`. |
| Dependências | 2 | Frágil | Sem pin, sem `pyproject.toml`, sem ambiente reprodutível. |

---

## 2. Dores reais — confirmadas por teste empírico

Testes de fumaça executados em `game_engine.py` e `dungeon_map.py` no ambiente do projeto.

### 2.1 Bugs de gameplay confirmados

1. **Level-up só sobe um nível por chamada** — `Character.gain_xp(9999)` em nível 1 retorna nível 2, nunca 5. O `if next_level in xp_thresholds` só testa o nível imediatamente seguinte. ([game_engine.py L294-307](../game_engine.py#L294-L307))
2. **Clérigo "Curar Ferimentos" não consome o turno corretamente** — o branch do CLERIGO em [game_engine.py L555-562](../game_engine.py#L555-L562) cura e cai no `_single_attack` no fim da função, então o personagem cura **e** ataca de graça no mesmo turno (gastando o uso especial). O comentário `*(Ainda pode atacar normalmente)*` não é uma decisão de design — é um bug por falta de `return`.
3. **`roll()` falha em algumas notações** — o parser usa `notation.split('d')[-1]` para detectar `-`, o que quebra com modificador zero ou notações estranhas. Coberto parcialmente no teste, mas não há validação de entrada.
4. **`use_potion` confunde "Pocao de Cura" e "Pocao de Cura x2"** — o `if "x" in item` casa **qualquer** "x", e o split ingênuo crasharia em `"Pocao Antitóxico x2"` ou similar se for adicionado depois. Acoplamento por string mágica.
5. **`generate_dungeon_map` pode silenciosamente perder bloqueios** — quando `lock_candidates` esvazia ele faz `continue` sem registrar; o jogador acaba com uma chave sem fechadura correspondente. Sem teste, sem log.
6. **HP exibido pode ficar `>` HP máximo após save/load** — `_deserialize_character` aceita `hp` arbitrário do JSON sem clamp. Vetor de save-edit trivial, e quebra em saves de versões antigas.
7. **`gemini_api_key` é gravada em texto puro no save** quando o usuário não explicita — embora o save corrente force `""`, o `load_game_state` lê e usa qualquer string, criando risco de leak se o save for compartilhado.

### 2.2 Dores arquiteturais

1. **`app.py` faz tudo** — UI, persistência, métricas, prompts, fallback, guardrails. Quase impossível testar isoladamente.
2. **Estado global via `st.session_state`** acoplado em todo lugar. Funções como `advance_room()`, `start_combat()`, `get_ai_response()` leem/mutam ~15 chaves cada. Sem contrato.
3. **Acoplamento UI ↔ regra** — `execute_player_turn` empurra mensagens de combate direto na UI; a engine deveria devolver eventos.
4. **Sem camada de testes** — qualquer refator quebra silenciosamente.
5. **Mensagens crescem indefinidamente** até `MAX_STORED_MESSAGES=120`; o resumidor é disparado, mas é **mais uma chamada LLM** por turno — e em [llm_metrics.csv](../llm_metrics.csv) já há falha 429 registrada por causa disso.
6. **Fallback Gemini→Ollama é "mágico"** — se o usuário não tem Ollama, a UX simplesmente quebra e o erro é técnico.
7. **Sem cache** — toda mudança em qualquer widget re-renderiza tudo, e `_check_llm_connection` chega a fazer requisições HTTP no path crítico.
8. **CSS injetado via `unsafe_allow_html`** funciona mas é frágil entre versões do Streamlit (>=1.30 já mudou seletores internos múltiplas vezes).

### 2.3 Dores de prompt/IA (a partir do CSV de métricas e leitura dos prompts)

1. **Prompt de sistema cresce a cada turno** (`character_sheet()` é re-renderizado inteiro + estado autoritativo + lock info + style + lembretes vitais), pagando tokens repetidos. Custou as ~5,9 KB que apareceram no 429.
2. **Sem JSON/structured output** — o "FORMATO_RESPOSTA" é só uma instrução textual; modelos pequenos (Gemini Flash Lite, Llama 3.1 8B) ignoram o esquema com frequência.
3. **Guardrail `_contains_manual_combat_math` é regex-frágil** — bloqueia palavras como "rolagem de ataque" e "d20(", mas também pode dar falso positivo em narrações legítimas que mencionem "CA: 15" como descrição de armadura.
4. **Resumidor dispara em qualquer falha sem retry estruturado** e a falha é silenciosa.
5. **Sem temperatura por tipo de chamada** — combate, sumarização e narrativa usam a mesma `temperature` configurada no slider; o resumidor força `0.2`, mas o resto compartilha o estado.
6. **Persona anchoring forte mas sem teste de regressão** — não há nenhum check automatizado garantindo que a IA continua em PT-BR e dentro do formato.

### 2.4 Dores de UX

1. **Sem feedback de progresso** durante chamadas de LLM além do `st.spinner` — em chamadas de 10s+ (visto no CSV) o usuário acha que travou.
2. **Painel de combate não mostra "log da rodada"** — mensagens vão direto pro chat, misturadas com narrativa, sem agrupamento.
3. **Mapa SVG quebra em dungeons grandes** (>10 salas com ramificação). Layout serpentina não escala.
4. **"Novo Jogo" apaga sem confirmar.**
5. **Sem export de transcrição** (apenas métricas).
6. **`README.md` cita `gemini-2.0-flash` em uma seção e `gemini-2.5-flash-lite` em outra**, e o save default ainda é `gemini-2.0-flash`. Inconsistência.

---

## 3. Referências externas usadas

Critério: práticas vigentes 2024–2026 aplicáveis a (a) prompt engineering para personagens persistentes, (b) LLM-as-Game-Master, (c) Streamlit em produção.

### 3.1 Prompt engineering

- **Anthropic — "Prompt engineering for business performance"** (2024). Reforça três técnicas que se aplicam diretamente ao `prompts.py`:
  - *Step-by-step / scratchpad* em tags como `<thinking>` antes do output final → melhora consistência de modelos pequenos. Hoje só temos `<FORMATO_RESPOSTA>`. <https://www.anthropic.com/news/prompt-engineering-for-business-performance>
  - *Few-shot* com exemplos do output esperado dentro de `<examples>`. Já temos um, vale ter 2-3 (combate vitorioso, sala de descanso, sala trancada).
  - *Prompt chaining* — separar "decidir o que acontece" de "narrar o que aconteceu". O combate já faz isso; explorar deveria também.
- **dair-ai Prompt Engineering Guide** (atualizado 2025). Catálogo canônico das técnicas (CoT, Self-Consistency, Tree-of-Thoughts, Generated Knowledge). Para um GM solo, **Self-Consistency** (gerar 3 variações curtas e escolher a melhor) e **Generated Knowledge** (pedir à IA para listar fatos do mundo antes de narrar) são as mais aplicáveis. <https://www.promptingguide.ai/techniques>
- **OpenAI Cookbook — Structured Outputs / Response Format**. Modelos compatíveis com `response_format={"type":"json_schema",...}` reduzem drasticamente parsing frágil. Gemini também suporta via OpenAI-compat. <https://platform.openai.com/docs/guides/structured-outputs>
- **Google — Gemini API quotas**. Free tier do `gemini-2.0-flash` foi a `0` para vários projetos — daí o 429 já registrado. Para v1.0, padronizar em `gemini-2.5-flash-lite` (cota mais alta) e remover o save default antigo. <https://ai.google.dev/gemini-api/docs/rate-limits>

### 3.2 LLM como Game Master

- **"CALYPSO: LLMs as Dungeon Masters' Assistants"** (Zhu et al., 2023, AIIDE). Mostra que LLMs funcionam melhor como **assistentes do Mestre** (sumarizar, propor, descrever) do que como autoridade de regras. Reforça a separação que já temos: regras na engine, narrativa na IA. <https://arxiv.org/abs/2308.07540>
- **"Player-Driven Emergence in LLM-Driven Game Narrative"** (Park et al., 2024). Sugere manter um **estado canônico estruturado** (entities, facts, beats) e re-injetá-lo a cada turno, em vez de confiar no contexto da conversa. É exatamente o que o `<ESTADO_AUTORITATIVO>` tenta fazer — mas hoje cobre só HP/CA/inventário; falta NPCs, fatos do mundo, decisões anteriores. <https://arxiv.org/abs/2404.17027>
- **AI Dungeon postmortems públicos** (Latitude, 2021–2023). Lições recorrentes: (i) sumarização forçada perde detalhes importantes — usar **memória estruturada** + sumário; (ii) bloquear o jogador nunca funciona, **redirecionar narrativamente** funciona; (iii) modo "world bible" sempre pinado.

### 3.3 Streamlit em produção

- **Streamlit docs — "Caching"** (`@st.cache_data` / `@st.cache_resource`). Hoje, `OpenAI(...)` é instanciado a cada `chat_completion`, e `_check_llm_connection` faz HTTP em path quente. <https://docs.streamlit.io/develop/concepts/architecture/caching>
- **Streamlit docs — "Fragments" (`@st.fragment`, 1.33+)**. Permite atualizar só o painel de combate sem re-rodar o script todo. Para v1.0 reduz piscar e latência percebida. <https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment>
- **Streamlit — "App testing"** (`AppTest`, 1.28+). Permite testes ponta-a-ponta sem browser. <https://docs.streamlit.io/develop/api-reference/app-testing>

### 3.4 Engenharia geral

- **"The Twelve-Factor App"** — config via env (não em JSON de save). <https://12factor.net/config>
- **OWASP Top 10 (2021)** — A03 Injection (chave Gemini em arquivo de save legível), A05 Security Misconfiguration. <https://owasp.org/Top10/>
- **PEP 621 + `pyproject.toml`** para empacotamento moderno.

---

## 4. Plano para v1.0

Princípio: **incremental, testável, sem reescrever**. Cada fase entrega valor sozinha e tem critério de saída.

### Fase 0 — Higiene (1 dia)
**Objetivo:** parar de operar no escuro.
- [ ] `pyproject.toml` com `ruff`, `pytest`, `pytest-cov`, deps pinadas.
- [ ] `pre-commit` com `ruff` e `ruff format`.
- [ ] GitHub Actions: lint + testes em push.
- [ ] `.env.example` (`GEMINI_API_KEY`, `OLLAMA_URL`).
- [ ] Remover save default com `gemini-2.0-flash`; padronizar em `gemini-2.5-flash-lite`.

**Critério de saída:** `pytest` roda (mesmo vazio), `ruff check .` passa.

### Fase 1 — Rede de segurança (1–2 dias)
**Objetivo:** travar comportamento atual antes de mexer.
- [ ] `tests/test_dice.py` — `roll()`, `roll_check()`, edge cases (modificador zero, negativo, 100x stress).
- [ ] `tests/test_character.py` — criação por classe/raça, `gain_xp` com várias escadas, `take_damage`/`heal` com clamp.
- [ ] `tests/test_combat.py` — `resolve_player_attack` para todas as 6 classes, `use_special=True/False`, garantir invariantes (HP nunca <0, special_uses nunca <0).
- [ ] `tests/test_dungeon.py` — `generate_dungeon_map` para 5/7/10 salas, garantir que toda chave tem fechadura e vice-versa, todo lock é alcançável.
- [ ] `tests/test_save_roundtrip.py` — serializar/desserializar e comparar.

**Critério de saída:** cobertura ≥ 70% em `game_engine.py` e `dungeon_map.py`.

### Fase 2 — Corrigir bugs confirmados (0,5 dia)
- [ ] Loop em `gain_xp` para subir múltiplos níveis.
- [ ] `return` no branch CLERIGO de `resolve_player_attack` (ou design intencional explicitado e testado).
- [ ] Validação robusta em `roll()` via regex.
- [ ] `use_potion` baseado em `Item` dataclass com `quantity:int` em vez de string.
- [ ] `_deserialize_character` faz clamp `hp = min(hp, max_hp)` e remove leitura da `gemini_api_key` do save.
- [ ] Em `generate_dungeon_map`, log warning quando bloqueio é descartado; nunca dar uma chave órfã.

**Critério de saída:** todos os 6 bugs cobertos por teste de regressão.

### Fase 3 — Refator da arquitetura (2–3 dias)
**Objetivo:** quebrar `app.py` sem mudar comportamento.

```
ai_dm/
├── ai_dm/
│   ├── domain/         # Character, Monster, DungeonMap (puro, sem Streamlit)
│   ├── engine/         # combat, exploration, leveling — devolvem eventos
│   ├── llm/            # client, prompts, guardrails, metrics
│   ├── persistence/    # save/load (JSON) + migrações por versão
│   └── ui/             # streamlit views + widgets + fragments
├── tests/
└── app.py              # entrypoint só monta a UI
```

- [ ] `engine` devolve `list[GameEvent]` — UI traduz para mensagens de chat. Remove acoplamento.
- [ ] `GameSession` dataclass como única fonte de verdade; `st.session_state` guarda **uma** instância.
- [ ] `persistence` ganha campo `schema_version` e função `migrate()`.

**Critério de saída:** `app.py` ≤ 300 linhas, todos os testes verdes.

### Fase 4 — IA mais robusta (2 dias)
- [ ] **Structured output**: usar `response_format` JSON Schema para `{titulo, narrativa, percepcao, opcoes:[]}`. Renderização via template no cliente.
- [ ] **Memória estruturada** além do summary: `WorldState{npcs:[], facts:[], decisoes:[]}` atualizado pela engine, injetado no prompt como JSON compacto.
- [ ] **Cache de prompt de sistema** — só o estado autoritativo varia turno a turno; a parte fixa entra uma vez (Gemini suporta context caching para prompts grandes; Ollama implícito).
- [ ] **Eval suite**: 10 cenários fixos (`tests/eval/scenarios.yaml`) rodados em CI manual contra Ollama + Gemini, gerando relatório de: PT-BR mantido, formato respeitado, sem emoji, sem cálculo manual de combate. Reportar pass/fail.
- [ ] Substituir `_contains_manual_combat_math` regex por **classificador estruturado** (chamada barata pedindo `{"contains_combat_math": bool}`) ou por uma allowlist mais conservadora.
- [ ] `temperature` por tipo de chamada (narração 0.8, sumário 0.2, combate 0.6) configurável.

**Critério de saída:** taxa de "formato respeitado" ≥ 95% no eval, prompt médio reduzido em ≥ 30%.

### Fase 5 — UX (1–2 dias)
- [ ] `st.fragment` no painel de combate (só re-renderiza ele).
- [ ] Streaming token-a-token (`stream=True` no OpenAI client) com `st.write_stream`.
- [ ] Botão "Exportar transcrição (Markdown)".
- [ ] Confirmação para "Novo Jogo" e "Carregar Jogo" sobrescrevendo estado em curso.
- [ ] Painel "Métricas de IA" com gráfico simples (`st.line_chart` da latência por chamada).
- [ ] Mapa: trocar layout serpentina por força-dirigido leve quando `len(rooms) > 10`.

### Fase 6 — Distribuição (0,5 dia)
- [ ] `Dockerfile` slim + `docker-compose.yml` com Ollama opcional.
- [ ] Deploy em Streamlit Community Cloud com `secrets.toml` de exemplo.
- [ ] `CHANGELOG.md` com versionamento semântico; tag `v1.0.0`.
- [ ] README reescrito: badges, GIF, seção "Para o artigo" mantida e atualizada (modelos atuais).

---

## 5. Definition of Done — v1.0

1. `pytest --cov` ≥ 80% nos módulos `domain` + `engine`.
2. `ruff check .` e `ruff format --check .` limpos no CI.
3. Eval suite rodando contra Ollama com **0 quebras de formato** em 10 cenários.
4. Nenhum dos 6 bugs do §2.1 reproduzível.
5. `app.py` ≤ 300 linhas; nenhum import circular.
6. README mostra como rodar com Docker em ≤ 3 comandos.
7. Save antigo (versão 0) carrega via `migrate()` sem perder personagem.
8. Latência mediana de narrativa em Ollama local ≤ baseline atual + 0% (refator não pode regredir).

---

## 6. Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Refator quebrar gameplay sutil | Alta | Fase 1 (testes) **antes** da Fase 3. |
| Gemini muda formato de erro / quota | Média | Centralizar parsing em `llm/errors.py` com testes contra fixtures. |
| Streamlit muda seletor CSS | Média | Mover estilo para `style.css` carregado via `st.markdown`, e degradar com graça. |
| Eval suite vira gargalo | Baixa | Rodar manualmente, não em cada push (workflow `workflow_dispatch`). |

---

## 7. O que **não** entra na v1.0

Para evitar escopo inflado:
- Multiplayer / persistência em servidor.
- Geração de imagens.
- Voz / TTS.
- Mais classes/raças/monstros (manter o set atual, focar em qualidade).
- Sistema de magias completo D&D 5e.

Fica para v1.1+.
