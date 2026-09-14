# V19 — Códigos e Grupos DRE auditáveis

## Objetivo
Retirar a organização contábil da dependência de alterações no código-fonte e permitir que o Administrador configure, pela interface, onde cada código oficial entra na DRE.

## Regras obrigatórias
- O catálogo de códigos é a fonte mestre e pode ser criado, corrigido, reativado ou inativado pela interface.
- Inativar um código nunca apaga lançamentos históricos.
- Um código oficial pode pertencer a **um único grupo DRE ativo por vez**.
- Tentativas de dupla vinculação são bloqueadas.
- O Administrador pode mover um código de grupo em operação única auditada.
- Toda alteração grava auditoria com estado anterior e novo estado.
- A tela mostra códigos configurados, sem grupo, inativos e duplicidades legadas.
- A DRE prioriza os vínculos configurados pela interface. Regras CSV antigas permanecem somente como fallback temporário para códigos ainda não configurados.

## Catálogo oficial
O catálogo inicial foi ampliado com a relação de códigos apresentada no documento `CÓDIGOS.pdf`, preservando códigos e descrições. O código 0811 permanece sinalizado como sem descrição no documento-fonte, sem adivinhação.

## Ajustes acumulados
- Relatório principal: Banco primeiro, Caixa depois; B amarelo e C verde.
- Monitoramento: status Normal/Atenção/Crítico visíveis por extenso, sem truncamento.
