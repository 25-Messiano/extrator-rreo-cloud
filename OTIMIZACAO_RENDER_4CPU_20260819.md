# Otimização Render - 4 CPUs / 8 GB

A execução agora usa perfil automático conforme a capacidade detectada no container.

## Divisão aplicada

| CPUs | Lote | RREO | FNDE/OCR | Gemini |
|---:|---:|---:|---:|---:|
| 1 | 6 | 2 | 1 | 1 |
| 2 | 10 | 4 | 2 | 1 |
| 3-4 | 12 | 6 | 3 | 2 |
| 5-8 | 16 | 8 | 4 | 2 |

Para o Pro Plus atual (4 CPUs / 8 GB), o perfil esperado é **Desempenho 4 CPUs**.

A opção `otimizacao_automatica` fica ativada em `config/sistema.json`. Ao voltar o Render para Standard, o app reduz sozinho a concorrência na próxima inicialização/deploy.
