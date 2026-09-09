# v1.3.7.1 — RREO SAFE REGISTRY

- Registro Mestre JSON cumulativo e persistente no Cloud.
- Atualização atômica por município; sync a cada 5, ao fim da UF e da rodada.
- Histórico consolidado das auditorias reais já executadas.
- Alias controlado novo: PRESIDENTE CASTELLO BRANCO/SC -> Presidente Castelo Branco.
- Nenhum alias novo é autoativado por aprendizado; propostas ficam para revisão.
- Cobertura estadual incompleta é registrada como CONCLUIDO_INCOMPLETO.

# v1.3.7 — RREO SAFE IDENTITY HARDENING

Versao de endurecimento de identidade criada a partir das rodadas reais estaduais.

Principais mudancas:
- elimina correspondencia municipal por substring;
- extrai identidade de cabecalho explicito com UF;
- canonicaliza contracoes como d'Oeste/DOESTE;
- inclui aliases controlados de variantes e nomes historicos comprovados;
- mantem comportamento fail-closed para desconhecidos/ambiguos;
- preserva dupla leitura financeira independente e travas pos-gravacao da v1.3.6.

Veja `docs/RREO_SAFE_V137.md`.
