# V12 — IA real para extratos bancários

## Objetivo
Integrar a OpenAI API ao fluxo 06 → 07 → 08 → 09 sem permitir postagem automática na base oficial.

## Arquitetura
- PDF: leitura multimodal nativa pela Responses API, inclusive scans; saída validada por JSON Schema.
- XLSX/CSV: parser determinístico preserva data/valor/natureza; IA apenas enriquece/classifica.
- Classificação: catálogo oficial de Códigos APLB e Pessoas/Entidades é enviado como universo fechado. A IA não pode inventar código cadastral.
- Segurança: `store=False`; nenhuma chave é gravada no repositório; `OPENAI_API_KEY` vem do ambiente Render.
- Modelo padrão: `gpt-5.6-luna`, configurável por `OPENAI_MODEL`.
- A IA sugere Código APLB, pessoa/entidade, especificação, confiança e justificativa.
- Duplicidade continua 100% determinística e autoritativa.
- Todo item nasce em conferência. A IA nunca chama `criar_lancamento`.
- Liberação para a base oficial continua sendo ação humana no módulo 08.

## Controles
- Divergência de competência gera alerta.
- Duplicado exato é bloqueado.
- Possível duplicidade exige conferência.
- Confiança IA < 80% recebe alerta destacado.
- Ausência de correspondência segura deve retornar código/pessoa vazios.
- Auditoria existente registra criação e liberação do lote.

## Homologação
A implementação de código está concluída, mas a homologação operacional deve ser feita com extratos bancários reais de formatos usados pela APLB antes de declarar o módulo 100% homologado.
