# v1.2.7 — Tipos de Rodada (2026-08-23)

- Novo seletor **Tipo de Rodada** no Painel Único:
  - **Rodada Nova**: parte sempre da planilha-base limpa, cria arquivo independente e não sobrescreve o master.
  - **Rodada de Correção**: força reprocessamento da seleção e, após leitura bem-sucedida, limpa os campos antigos da fonte (RREO/FNDE) antes de gravar os novos valores.
  - **Rodada de Incrementação**: preserva o master e pula apenas o que já está concluído.
- Incrementação reabre automaticamente município antes marcado `SEM_PDF` quando um PDF novo passa a existir no Cloud.
- Rodadas Novas são salvas em `PLANILHAS_PROCESSADAS/RODADAS/<ano>/`, com nome único por data/hora.
- Correção e Incrementação mantêm backup técnico do master antes da alteração.
- Tipo da rodada incluído no histórico de jobs e na auditoria do Excel.
- Testes adicionados para política de rodadas, limpeza seletiva de RREO/FNDE e novo PDF em incrementação.

# v1.2.6 - Municípios oficiais e recuperação automática do app

- Corrige estado visual obsoleto no seletor de municípios: o código IBGE passa a ser a chave oficial e o widget é versionado por ano/UF.
- Elimina casos como `Alcobaça - Bacharelado (2900801)`; a fonte continua sendo a matriz oficial (`Alcobaça/BA`).
- Adiciona `core/app_recovery.py`: a cada mudança detectada no projeto, gera automaticamente `RECUPERACAO_APP.txt` e `RECUPERACAO_APP.py` e envia ao Cloud Storage.
- O `.py` de recuperação contém snapshot compactado autossuficiente dos arquivos do app e pode reconstruir o projeto.
- Backups ficam em `99_BACKUP_RECUPERACAO_APP/HISTORICO/` e a versão mais recente em `99_BACKUP_RECUPERACAO_APP/ULTIMO/`.
- Credenciais, caches, logs temporários e bancos locais de usuários/runtime são excluídos por segurança.

# v1.2.5 - Relatórios PDF de inventário do Cloud

- Dois relatórios no Painel Único: Brasil inteiro e por estado.
- PDF com CIDADE, ESTADO, RREO e FNDE, usando as mesmas regras de identificação do app.
- Inventário consulta apenas a existência dos arquivos no Cloud; não executa OCR, Gemini ou extração financeira.
- Cabeçalho repetido, resumo de cobertura e download direto no painel.
- Dependência `reportlab` adicionada para geração programática dos PDFs.

## 2026-08-19 — Execução nacional RREO + FNDE

- `Todos os Estados` agora percorre explicitamente as 27 UFs oficiais, mesmo quando uma pasta RREO/FNDE estiver ausente no Cloud.
- Brasília/DF é carregada para processamento municipal com o código IBGE `5300108`; a linha agregada `Distrito Federal/DF` permanece fora da fila.
- Lotes RREO/FNDE possuem timeout configurável (`timeout_lote_segundos`, padrão 420s) para impedir que um PDF bloqueie todo o Brasil.
- O Excel parcial é disponibilizado desde a preparação e salvo novamente ao final de cada lote.
- Operações do Google Cloud Storage e OCR Tesseract passam a ter limites de espera defensivos.
- Configuração `fnde_todos_estados` ativada.

# Entrega inicial

- Novo nome: `extrator-rreo-cloud`.
- Armazenamento exclusivo no Google Cloud Storage.
- Entrada principal na raiz: `app.py`.
- Página `4_Arquivos_Cloud.py` para listar PDFs e planilhas processadas.
- Extração RREO com Gemini e fallback local corrigido para ler o segundo valor monetário da linha.
- Planilha-base incluída em `data/`.
- Dockerfile e `render.yaml` prontos para novo serviço no Render.
- Script de validação em `scripts/validate_project.py`.
## Extração visual FNDE + logs separados

- Gemini Vision passa a ser a leitura principal dos PDFs FNDE em imagem.
- OCR local Tesseract (por+eng) atua como fallback.
- Repetição automática e troca de modelo Gemini.
- Progresso incremental e checkpoints configuráveis.
- Abas LOG_FNDE e LOG_RREO separadas.
- Abas AUDITORIA e MUNICIPIOS_NAO_ENCONTRADOS preservadas.
- Modelo padrão atualizado para gemini-3.6-flash.


## 2026-08-19 - Otimização adaptativa por CPU
- Detecção automática da capacidade da instância do Render.
- Perfil de 4 CPUs: lote 12, RREO 6, FNDE/OCR 3 e Gemini 2.
- Perfis menores aplicados automaticamente ao retornar para 1 ou 2 CPUs.
- Concorrência do Gemini passa a acompanhar o perfil ativo.
- Painel exibe o perfil de desempenho realmente utilizado durante os lotes.

## 2026-08-19 — Excel mestre e atividade persistente
- Um único `RREO_FNDE_BRASIL_MASTER_<ANO>.xlsx` passa a receber todas as rodadas.
- Município/estado/Brasil inteiro atualizam o mesmo master.
- Registro persistente por ano + código IBGE, com status RREO/FNDE, erros e tentativas.
- Municípios já concluídos são pulados automaticamente, com opção de reprocessamento forçado.
- `SEM_PDF` é tratado como fonte verificada e não bloqueia o processamento nacional.
- Pausa segura e continuação usando master + registro persistente.
- Backups técnicos automáticos do master antes de nova rodada.
- `LOG_ATIVIDADE_<ANO>.xlsx` separado para conferência.
- Página Histórico ampliada com execuções e atividade por município.
- Checkpoints técnicos por lote desativados por padrão para evitar acúmulo de arquivos.

## 1.2.4 - Identificação Cloud unificada (20/08/2026)
- RREO/FNDE: identificação por IBGE, nome+UF e similaridade segura.
- Fallback recursivo por ano quando a pasta estadual não segue o padrão.
- Botão para atualizar imediatamente a listagem do Cloud.
- Cache de fallback por ano para não repetir varredura nacional por UF.
- Healthcheck Docker compatível com PORT do Render.
- Teste explícito de Raposos/MG e pastas com UF+ano.

## 2026-08-24 - Validação dupla e recursos adaptativos
- Segunda leitura obrigatória antes de considerar valores RREO/FNDE validados.
- Divergências de valores são bloqueadas e registradas; somente campos confirmados são gravados.
- FNDE usa canal de verificação alternativo (OCR/Gemini) e desempate quando necessário.
- RREO relê o PDF com parâmetros independentes e usa desempate apenas nas divergências.
- Perfil de workers agora se adapta à quantidade de CPUs do plano Render.
- Identificação de municípios ficou mais tolerante; diferenças de grafia/acentuação não devem bloquear processamento sem ambiguidade real.
