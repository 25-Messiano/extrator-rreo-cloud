from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_versao_e_estrutura():
    assert (ROOT/'VERSION').read_text().strip()=='V26.10'
    ent=(ROOT/'models/entities.py').read_text(encoding='utf-8')
    for nome in ['class ParametroFolha','class HistoricoSalarial','class CalendarioFolha','class FolhaSnapshot','class ChecklistFolha']:
        assert nome in ent

def test_ui_tem_vigencias_checklist_e_ajuda():
    txt=(ROOT/'pages/40_Folha_Pagamento.py').read_text(encoding='utf-8')
    for trecho in ['Parâmetros e Vigências','Calendário','Conferência/Fechamento','Checklist de fechamento','❓']:
        assert trecho in txt

def test_servico_preserva_snapshot_e_transicoes():
    txt=(ROOT/'services/folha_pagamento.py').read_text(encoding='utf-8')
    for trecho in ['def salvar_parametro','def nova_vigencia_salarial','def transicionar_folha','FolhaSnapshot','CHECKLIST_PADRAO']:
        assert trecho in txt
