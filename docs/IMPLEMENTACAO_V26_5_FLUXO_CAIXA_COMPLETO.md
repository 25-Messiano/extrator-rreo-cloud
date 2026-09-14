# V26.5 — Fluxo de Caixa completo e datas brasileiras

## Objetivo
Implementar a estrutura prevista no organograma para Fluxo de Caixa Realizado e Projetado, mantendo isolamento por tesouraria e sem alterar a natureza oficial dos lançamentos.

## Datas
A interface e os relatórios passam a exibir datas no padrão brasileiro `DD/MM/AAAA`. O armazenamento interno do banco permanece no tipo DATE próprio do banco.

## Fluxo realizado
- Origem exclusiva em lançamentos oficiais: APROVADO, CONCILIADO e FECHADO.
- Visões: dia, semana, mês, trimestre, semestre e ano.
- Filtros: Banco/Caixa, Código, DRE, Centro de Custo, Favorecido e Tipo Entrada/Saída.
- Indicadores: entradas, saídas, resultado, saldo inicial e saldo final.
- Gráficos de entradas/saídas e evolução de saldo.
- Exportação PDF e Excel conforme filtros.

## Fluxo projetado
- Data prevista, valor, natureza e descrição.
- Conta Banco/Caixa opcional.
- Classificação por Código; DRE é derivada do vínculo oficial do código.
- Centro de custo e Favorecido.
- Cenários REALISTA, PESSIMISTA e OTIMISTA.
- Probabilidade da previsão.
- Recorrência opcional e frequências: semanal, quinzenal, mensal, bimestral, trimestral, semestral e anual.
- Data final da recorrência.
- A recorrência é expandida na consulta sem transformar previsão em lançamento oficial.

## Comparativo
A tela compara projetado x realizado pelo mesmo período de agregação e apresenta o desvio do resultado.

## Alertas
- DÉFICIT: saldo projetado abaixo de zero.
- SALDO INSUFICIENTE: margem projetada muito baixa diante das saídas do período.

## Ajuda
Botão `❓` abre janela flutuante com regras completas de uso do módulo.

## Patrimônio
Também foi ajustada a apresentação visual das datas do Patrimônio para `DD/MM/AAAA`, sem alterar os valores armazenados no banco.

## Migração de banco
Aditiva na tabela `fluxo_projetado`: conta financeira, centro de custo, favorecido, cenário, frequência, recorrência e data final da recorrência.
