# MAESTRO IA — arquitetura de homologação e modo sombra

## Objetivo
Adicionar inteligência adaptativa ao Painel Único de Extração e à Central de Correções sem permitir que IA altere dados oficiais ou código de produção de forma autônoma.

## Papéis
- Python: motor determinístico, persistência, planilhas, checkpoints e regras oficiais.
- Gemini: Especialista de Extração para casos difíceis, layouts não reconhecidos e releitura dirigida.
- OpenAI Agents SDK: Supervisor/Orquestrador para revisar falhas, comparar evidências, decidir escalonamento e propor patches candidatos.
- Validadores: regras determinísticas de consenso e integridade.
- Memória Operacional: casos, decisões e estratégias validadas em SQLite.
- Laboratório: testes de carga, regressão, mutação e avaliação antes de qualquer publicação.

## Modo sombra
MAESTRO_IA_SHADOW_MODE=true é a configuração inicial obrigatória. Nesse modo:
1. observa o resultado do motor oficial;
2. registra casos na memória;
3. pode consultar especialistas quando habilitado;
4. produz decisões de auditoria;
5. nunca altera workbook, JSON oficial, status de processamento ou Git.

## Autoaperfeiçoamento controlado
Extrator falha -> Gemini analisa -> Supervisor revisa -> validadores conferem -> memória aprende.
Se houver deficiência de código, é criado apenas PATCH_CANDIDATO_*.json. O campo can_apply_automatically é sempre false.
A publicação exige homologação e aprovação humana.

## Variáveis
- OPENAI_API_KEY: segredo fora do Git/ZIP.
- MAESTRO_IA_ENABLED=true
- MAESTRO_IA_SHADOW_MODE=true
- MAESTRO_IA_LIVE_AI=false inicialmente
- MAESTRO_OPENAI_MODEL: modelo do Supervisor
- MAESTRO_MEMORY_DB=data/maestro_ia_memory.sqlite3
- MAESTRO_PATCH_DIR=data/maestro_ia_patch_candidates

## Critério de promoção
Modo sombra -> assistido somente depois de: testes unitários, carga Brasil, PDFs padrão-ouro, memória, regressão, mutation testing e aprovação humana.
