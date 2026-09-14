# V10 — Competência, Pessoas/Entidades e Antiduplicidade

- Importação exige exercício, mês de competência e conta bancária.
- Datas originais do extrato são preservadas; datas fora da competência geram aviso e passam por conferência.
- Cadastro único de Pessoas e Entidades gera ID automático por tipo (COL/FOR/PRE/ENT/SIN/ORG/CAD).
- O ID individual é independente do Código APLB/DRE.
- Lançamentos podem vincular `favorecido_id` sem perder o nome textual histórico.
- DUPLICADO_EXATO: mesma data, valor, B/C, natureza, código, pessoa/entidade, especificação, documento e conta -> bloqueado.
- POSSIVEL_DUPLICIDADE: mesma data/valor/B-C/natureza, mas diferenças nos campos de identificação -> conferência humana.
- DISTINTO: segue o fluxo normal.
- Nenhum extrato entra diretamente na base oficial: Extrato -> Conferência -> Aprovação -> Base Oficial.
