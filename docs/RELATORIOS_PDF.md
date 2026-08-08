# Relatórios em PDF

A página **Relatórios** gera PDFs sob demanda usando a mesma base SQLite do calendário. Nenhuma data é recalculada para o relatório.

## Tipos implementados

- Relatório Mensal do Calendário;
- Relatório Anual;
- Correspondência G <-> M;
- Fases da Lua;
- Estações do Ano;
- Festas Bíblicas;
- Data Específica;
- Intervalo Personalizado;
- Auditoria das Fontes.

## Regras

- Mensal, Anual e Intervalo podem ser exportados como G + M, somente G ou somente M.
- Lua e Estações aceitam um ano como recorte.
- Correspondência aceita intervalo e limita a saída a 10.000 dias.
- Intervalo detalhado limita a saída a 5.000 dias.
- Festas Bíblicas incluem apenas `STATUS=ATIVO`.
- `AGUARDA_REGRA` nunca é exibido.
- A Páscoa é deduplicada quando coincide com o catálogo de festas.
- O PDF não expõe bucket, paths, credenciais, tokens ou secrets.
- O rodapé usa somente: `Fonte dos dados: registros oficiais do calendário.`

## API

`POST /api/relatorios/pdf`

O corpo é JSON e pode conter:

- `tipo`
- `calendario`: `both`, `g` ou `m`
- `referencia`: `g` ou `m`
- `ano`
- `mes`
- `data`
- `inicio`
- `fim`
- `lua`
- `estacoes`
- `pascoa`
- `festas`

A resposta de sucesso é `application/pdf` com `Content-Disposition: attachment`.
