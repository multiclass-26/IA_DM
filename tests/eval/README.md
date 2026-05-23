# Avaliação manual da LLM

Os arquivos aqui são **cenários de avaliação semi-manual** para o Mestre
Sombrio. Não são executados pelo `pytest` (não queremos chamar a LLM no CI
do PR — custa dinheiro e é flaky).

Para rodar manualmente:

```powershell
# .venv ativada, com GEMINI_API_KEY exportada
python -m ai_dm.eval.runner --provider gemini --model gemini-2.5-flash-lite
```

(o `runner` será implementado conforme houver demanda; por ora os
cenários servem como **especificação de comportamento** auditável.)
