# v1.3.4 — Central de Correções: reconstrução real das rodadas estaduais

- Corrige o caso em que a Central reconstruía `0 município(s)` apesar de existirem resultados no Cloud.
- Reconhece também saídas estaduais de Rodada Nova no padrão `RREO_UF_ANO_Bx_RODADA_NOVA_...xlsx`.
- Mantém reconhecimento das saídas `_ESTADO_UF_...xlsx`.
- Quando os estados foram processados individualmente por Incrementação/Correção e acumulados no MASTER, a Central usa `RREO_FNDE_BRASIL_MASTER_<ano>.xlsx` como fonte retroativa e separa os municípios por UF.
- O MASTER é apenas lido; nenhuma planilha existente é alterada durante a reconstrução.
- 44 testes automatizados aprovados.

# v1.3.2 — Central de Correções

- Nova página independente **Central de Correções** no menu lateral, logo abaixo do Painel único.
- Reconstrução retroativa de JSONs por UF a partir das planilhas estaduais já existentes no Cloud.
- Catálogo nacional de correções salvo sem alterar as planilhas processadas.
- Relatório `PENDENCIAS_BRASIL_<ano>.xlsx` com status RREO/FNDE, existência de PDF e origem.
- Correção por IBGE prepara o mesmo motor oficial em **Rodada de Correção**, evitando duplicar o extrator.
- Planilhas master, multiestado e relatórios são ignorados na reconstrução para não misturar bases.

# v1.3.1 — RREO exclusivo APPDOWELEVER, sem fallback antigo

- Origem RREO única: `appdowelever-arquivos/01_Arquivo_dos_Estados_RREO_e_FNDE/4_APPDOWELEVER/RREO/{ANO}/{ESTADO}/B{N}/`.
- Removido todo fallback RREO para bucket/prefixos antigos.
- Loga `gs://bucket/prefixo` exato antes de processar cada estado.
- Quando não houver PDF na fonte oficial, registra `PDF NÃO ENCONTRADO NA FONTE APPDOWELEVER`.
- Falhas de permissão/conexão na fonte oficial deixam de ser mascaradas por fallback.
- A remoção das varreduras recursivas antigas reduz I/O e acelera a listagem do RREO.
- Mantidos JSON sequencial por estado, proteção de RAM e Estados selecionados.

# v1.3.0 — Estados selecionados + JSON sequencial

- Nova abrangência **Estados selecionados** no Painel Único.
- Permite marcar 2, 3 ou quantas UFs forem necessárias.
- As UFs selecionadas são processadas estritamente em sequência; nenhum lote mistura estados.
- Cada UF concluída persiste seu próprio JSON/checkpoint antes de liberar a próxima.
- A retomada restaura somente as UFs selecionadas para aquela execução.
- Ao final, os estados escolhidos são consolidados no mesmo Excel da rodada.
- O identificador da execução inclui a seleção de UFs/municípios, evitando reaproveitar checkpoint de outra combinação.
- Mantidos os perfis de proteção de memória da v1.2.9.

# v1.2.9 — Proteção de memória no Render (2026-09-01)

- Detecta o limite de RAM do container via cgroup e aceita `APP_MEMORY_LIMIT_MB` como override.
- Em até 768 MB usa lote unitário e apenas 1 worker pesado por fonte.
- Em até 1,5 GB mantém execução conservadora; RREO+FNDE deixam de rodar simultaneamente.
- Execução nacional gera lotes sob demanda, sem duplicar todos os lotes do Brasil em memória.
- Após concluir cada UF, persiste o JSON, descarta índices/resultados daquele estado e força coleta de lixo.
- Resultados dos workers RREO não carregam mais o texto completo do PDF após a auditoria interna.
- O Excel nacional não é copiado para `st.session_state` a cada lote; o download binário só é carregado no final e dentro de limite configurável.
- Pendências nacionais são registradas antes da liberação dos índices, preservando a auditoria.

# v1.2.8 — Identidade oficial e deduplicação segura (2026-08-24)

- A **planilha-base passa a ser a autoridade absoluta** para nome, UF e código IBGE do município de destino.
- O nome do PDF no Cloud serve somente para localizar/auditar o arquivo e nunca pode renomear município nem trocar o IBGE oficial da planilha.
- Se o PDF tiver **nome correto e IBGE errado**, o app associa pelo nome oficial da base, preserva o IBGE correto e registra `IBGE_ARQUIVO_DIVERGENTE`.
- Códigos digitados com 8 algarismos por engano no filename também são removidos da comparação do nome (ex.: `22708907_Satuba`).
- A busca por UF no Cloud considera primeiro a pasta estadual, evitando que um IBGE errado no filename esconda um PDF existente.
- Duplicatas do mesmo município são removidas da fila: cópia binária vira `DUPLICADO_IDENTICO`; arquivos diferentes viram `DUPLICADO_CONFLITANTE`.
- Duplicatas **não são apagadas fisicamente do Cloud** nesta rotina; apenas um candidato é processado e todos os demais ficam auditados.
- Logs RREO/FNDE passam a registrar IBGE presente no arquivo, divergência com a base, método/confiança da associação e duplicados ignorados.
- Testes cobrem Satuba/AL com IBGE errado, código de 8 dígitos, duplicatas idênticas/conflitantes e fallback por pasta de UF.

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

## v1.2.8 - Novo acervo APPDOWELEVER + JSON nacional por estado

- RREO passa a procurar primeiro no bucket `appdowelever-arquivos`.
- Prefixo configurável: `01_Arquivo_dos_Estados_RREO_e_FNDE/4_APPDOWELEVER/`.
- Estrutura de leitura: `ANO/PASTA_DO_ESTADO/B1..B6/PDF`.
- Painel ganhou seleção explícita de bimestre RREO.
- Fallback integral para o acervo antigo quando a nova fonte não estiver disponível.
- Execução `Todos os Estados` agora agenda lotes estritamente por UF; um estado não divide lote com o seguinte.
- Ao terminar cada UF, grava JSON persistente com dados/IBGE/arquivos/erros no Cloud.
- Em retomada nacional, estados concluídos são reconstruídos dos JSONs antes de continuar.
- Durante execução nacional, o Excel fica local/parcial; o Excel consolidado é publicado no Cloud somente no final.
- O ID do trabalho nacional inclui o bimestre para impedir reaproveitamento de checkpoint de outro período.

# v1.3.4 — Central de Correções: busca direta em RODADAS/<ano>
- A Central deixa de varrer toda a árvore 03_PLANILHAS_PROCESSADAS e consulta diretamente RODADAS/<ano>/.
- Reconhece RREO_UF_ANO_B6_RODADA_NOVA_*.xlsx e seleciona a mais recente por UF/fonte.
- O MASTER passa a ser fallback por caminho conhecido, sem busca ampla.
- A interface informa quantas planilhas estaduais foram encontradas.

## Laboratório MAESTRO IA — modo sombra
- Núcleo MAESTRO IA adicionado sem alterar o resultado oficial.
- OpenAI Supervisor preparado via Agents SDK e variável OPENAI_API_KEY.
- Gemini definido como Especialista de Extração; chamadas reais continuam desativadas no modo sombra inicial.
- Memória operacional SQLite auditável.
- Propostas de patch nunca são aplicadas automaticamente.
- Hooks não bloqueantes no Painel Único e na Central de Correções.
- Central otimizada para leitura XLSX streaming e MASTER adiado para fallback.
- Evals locais, mutation gate e workflow de homologação adicionados.
