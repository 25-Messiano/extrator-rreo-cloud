# Evolução: Excel Mestre + Registro de Atividade

Data: 19/08/2026

## Objetivo

Substituir a geração de um Excel novo por rodada por um fluxo incremental, com um único arquivo mestre por ano e registro persistente do que já foi processado.

## Excel mestre

- Arquivo operacional único por ano: `RREO_FNDE_BRASIL_MASTER_<ANO>.xlsx`.
- Município, estado ou Brasil inteiro atualizam o mesmo arquivo.
- O master é baixado do Cloud no início da rodada e reenviado ao final de cada lote concluído.
- Antes de uma nova rodada, quando o master já existe, é criado um backup técnico no Cloud.
- O master funciona como checkpoint durável. Checkpoints técnicos por lote foram desativados por padrão para evitar centenas de arquivos visíveis.

## Registro de atividade

Nova tabela `municipio_atividade`, identificada por `ano + código IBGE`, com:

- UF e município;
- status RREO;
- status FNDE;
- status geral;
- último erro;
- número de tentativas;
- data/hora da última atualização.

Status de fonte:

- `OK`: documento encontrado e processado;
- `SEM_PDF`: fonte verificada, mas PDF não fornecido (é terminal e não bloqueia o restante do Brasil);
- `ERRO`: documento/tarefa falhou e pode ser reprocessado;
- `PENDENTE`: ainda não verificado;
- `NA`: compatibilidade interna.

O status geral é `PROCESSADO` quando RREO e FNDE estão em estados terminais (`OK` ou `SEM_PDF`).

## Evitar reprocessamento

Por padrão, municípios já concluídos para a operação selecionada são pulados. Há uma opção `Reprocessar municípios já concluídos` para forçar nova leitura.

Uma rodada RREO isolada preserva o status FNDE anterior, e uma rodada FNDE isolada preserva o status RREO anterior.

## Pausa e retomada

O antigo botão de cancelamento foi convertido para pausa segura. Ao pausar, o master atual é sincronizado e a execução fica registrada como `PAUSADO`.

Após uma perda de sessão ou reinício, a próxima abertura oferece `Continuar / atualizar`. O sistema baixa o master e pula automaticamente o que já foi persistido. No máximo o lote que ainda não havia sido sincronizado precisa ser refeito.

Observação: esta versão torna a execução retomável e resistente à perda da sessão, mas não transforma o Streamlit em um worker externo independente. Um restart do próprio processo interrompe o lote corrente; a continuação é feita pelo registro persistente + Excel mestre.

## Histórico e conferência

A página Histórico agora possui abas para:

- Execuções persistentes;
- Municípios e seus status por ano/UF;
- Histórico técnico anterior.

Também é mantido no Cloud um arquivo de conferência `LOG_ATIVIDADE_<ANO>.xlsx`, separado do Excel mestre.

## Segurança operacional

A atividade de um lote só é marcada no banco depois que o Excel mestre daquele lote é enviado com sucesso ao Cloud. Se o upload falhar, a próxima rodada não pula esses municípios, evitando status falso de conclusão.

## Validação

- `pytest`: 9 testes aprovados.
- `python -m compileall`: aprovado.
- `scripts/validate_project.py`: aprovado.
