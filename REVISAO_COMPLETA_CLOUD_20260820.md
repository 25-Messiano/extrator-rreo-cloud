# Revisao completa Cloud - 20/08/2026

## Objetivo
Tornar a descoberta de RREO/FNDE tolerante a variacoes seguras de nomes de pastas e arquivos sem associar documentos ao municipio errado.

## Regra unificada de identificacao
1. Codigo IBGE municipal de 7 digitos, quando presente, tem prioridade absoluta.
2. Sem IBGE, usa nome oficial normalizado dentro da UF.
3. Como ultimo recurso, similaridade alta (88%) dentro da mesma UF.
4. Casos ambiguos nao sao associados automaticamente.

## Descoberta no Google Cloud Storage
- RREO e FNDE tentam primeiro a pasta estadual convencional.
- Se a pasta nao existir ou estiver vazia, o app varre somente o modulo/ano correspondente e filtra por UF usando IBGE, filename e caminho completo do blob.
- Estruturas legadas continuam suportadas como ultimo recurso.
- Pastas como `31_Minas Gerais_MG_2025` e `FNDE_Minas_Gerais_MG_2025` sao aceitas.

## Uploads novos
- Cache da lista de PDFs RREO reduzido para 30 segundos.
- Adicionado botao `Atualizar arquivos do Cloud` para limpar o cache imediatamente.

## FNDE
- `FNDE_2025_3153905_Raposos - MG.pdf` e identificado diretamente pelo IBGE 3153905.
- Arquivos FNDE sem IBGE podem ser associados por nome + UF, desde que a correspondencia seja segura.

## RREO
- Usa o mesmo identificador unificado para filename.
- O conteudo interno continua servindo apenas para auditoria e nao troca silenciosamente o municipio associado.

## Ambiente
- `requirements.txt` revisado: as dependencias usadas pelo projeto permanecem declaradas.
- Dockerfile atualizado com healthcheck respeitando a porta `PORT` do Render.
- `.dockerignore` e `.gitignore` impedem envio de caches Python e arquivos locais desnecessarios.

## Validacao local
- `python -m compileall -q .`
- `python scripts/validate_project.py`
- `pytest -q`
- 15 testes aprovados, incluindo Raposos/MG e fallback de pasta fora do padrao.

## Limite da validacao
A sessao de revisao nao possui as credenciais reais do bucket/Gemini do Render. Por isso a varredura real do bucket deve ser confirmada apos o deploy, usando o botao `Atualizar arquivos do Cloud` e o caso Raposos/MG.
