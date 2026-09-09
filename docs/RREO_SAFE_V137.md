# RREO SAFE v1.3.7

A v1.3.7 consolida os gargalos descobertos nas rodadas reais de RO, SE, PI, PE, GO, AL, SP, SC, RS, RN, RJ e PR.

## Alteracoes centrais

- Remove a identificacao de municipio por substring em todo o texto.
- Le o municipio somente de candidatos de cabecalho explicito `MUNICIPIO - UF` ou rotulos equivalentes.
- Corrige contracoes oficiais como `d'Oeste -> DOESTE`, `d'Agua -> DAGUA`, `d'Arca -> DARCA` sem fuzzy solto.
- Adiciona aliases controlados para variantes/historicos comprovados em PDFs oficiais.
- IA nao libera municipio por similaridade: a resposta da IA tambem precisa resolver por nome canonico ou alias controlado.
- Mantem fail-closed: nome desconhecido, ambiguo ou nao identificado fica bloqueado.
- Preserva dupla leitura financeira independente pdfplumber + PyMuPDF geometrico.
- Adiciona funcao de integridade de lote estadual para comparar municipios esperados x nomes de PDFs encontrados.

## Gargalos cobertos

- Nomes curtos dentro de nomes maiores: `Ita/Itajai`, `Itati/Itatiba`, `Tapejara/Itapejara d'Oeste`, `Perola/Perola d'Oeste`, `Rancho Alegre/Rancho Alegre d'Oeste`.
- Contracoes e pontuacao: `d'Oeste`, `d'Agua`, `d'Arca`, `d'Ajuda`.
- Variantes ortograficas controladas: `Chiapetta/Chiapeta`, `Moji/Mogi Mirim`, `Florinia/Florinea`, `Sao Luis/Sao Luiz do Quitunde`.
- Denominacoes historicas controladas: `Januario Cicco/Boa Saude`, `Augusto Severo/Campo Grande`.

## Regra de seguranca

Nenhuma similaridade aproximada isolada autoriza gravacao. Quando a identidade nao puder ser provada por cabecalho + UF + nome canonico/alias controlado, o RREO permanece `PENDENTE_CONFERENCIA`.
