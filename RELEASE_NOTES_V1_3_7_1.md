# v1.3.7.1 — RREO SAFE REGISTRY

- Registro Mestre JSON cumulativo e persistente.
- Gravação atômica por município.
- Sincronização Cloud a cada 5 municípios, ao fim da UF e ao fim da rodada.
- Merge otimista por generation do Google Cloud Storage.
- Seed histórico consolidado das auditorias reais já executadas.
- Registro de cobertura oficial x PDFs encontrados.
- Registro de SHA-256, fingerprint, valores, segundo leitor, identidade e pós-gravação.
- Aprendizado de novos aliases fica em fila de proposta; nunca afrouxa a trava automaticamente.
- Alias controlado adicionado: Presidente Castello Branco/SC -> Presidente Castelo Branco/SC.
