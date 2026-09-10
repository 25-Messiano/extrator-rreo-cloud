# RREO SAFE Registry v1.3.7.1

A v1.3.7.1 adiciona um Registro Mestre JSON persistente e cumulativo ao RREO SAFE.

## Regras

- Cada município processado gera/atualiza um registro atômico local.
- O registro é sincronizado com Google Cloud Storage a cada 5 municípios e obrigatoriamente ao concluir cada UF e a rodada.
- O JSON guarda versão do motor, ano, bimestre, cobertura estadual, PDF, SHA-256, fingerprint do resultado, identidade, dois leitores, divergências, campos ausentes, status SAFE, pós-gravação e erros.
- O histórico nunca é apagado; uma nova rodada cria uma chave por job+UF.
- O upload usa precondição de geração do GCS e merge em caso de concorrência para evitar sobrescrita silenciosa.
- Novos aliases descobertos podem ser registrados como proposta, mas **não são ativados automaticamente**. Isso preserva a política fail-closed.
- A tabela de aliases controlados continua separada e auditável.

## Local do mestre no Cloud

`01_Arquivo_dos_Estados_RREO_e_FNDE/04_AUDITORIA_RREO_SAFE/REGISTRO_MESTRE_RREO_SAFE.json`

## Seed histórico

O pacote inclui um seed consolidado das rodadas já realizadas em RO, SE, PI, PE, GO, AL, SP, SC, RS, RN, RJ, PR e MT, incluindo a repetição de SC na v1.3.7.
