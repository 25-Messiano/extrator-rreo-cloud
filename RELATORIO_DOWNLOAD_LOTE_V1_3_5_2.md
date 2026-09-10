# Homologação — v1.3.5.2

## Implementado
- Página independente `📦 Download em Lote` preservada no menu lateral.
- Atalho redundante `📦 Abrir Download em Lote` preservado na tela inicial.
- Nova escolha: `PDFs RREO` ou `Planilhas processadas`.
- Planilhas: `Estaduais mais recentes`, `Todas as Rodadas Novas`, `MASTER nacional`.
- Abrangência Estado/Brasil quando aplicável.
- Estaduais mais recentes: seleciona a última planilha por UF e fonte, evitando duplicar rodadas antigas.
- MASTER: usa o arquivo nacional oficial do ano.
- ZIP salvo em `03.../04_DOWNLOADS_LOTE/PLANILHAS/<ANO>/` no bucket de resultados.
- Arquivos originais são somente lidos; nenhuma planilha é sobrescrita.
- Link assinado temporário para download sem carregar o ZIP inteiro na RAM do Streamlit.

## Provas de publicação
- Sidebar mostra `v1.3.5.2`.
- Menu contém `Download em Lote`.
- Home contém `Abrir Download em Lote`.
- Rodapé da página contém `v1.3.5.2`.
- `DEPLOY_CHECK_V1_3_5_2.txt` e `DEPLOY_PROOF_V1_3_5_2.sha256` incluídos.

## Testes
- `pytest -q`: 62 passed.
- `python -m compileall -q .`: PASS.
- `python scripts/validate_project.py`: PASS.

## Observação operacional
A homologação local valida lógica, estrutura e empacotamento. O teste real de GCS/Render deve ser feito após o deploy, primeiro confirmando visualmente `v1.3.5.2`, depois conferindo os arquivos encontrados e só então preparando um ZIP pequeno de um Estado.
