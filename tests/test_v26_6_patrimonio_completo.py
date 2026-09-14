from pathlib import Path
from datetime import date


def test_version_266():
    root=Path(__file__).resolve().parents[1]
    assert (root/'VERSION').read_text(encoding='utf-8').strip()in ('V26.7','V26.8', 'V26.9', 'V26.10')


def test_patrimonio_model_campos_e_anexo():
    from models.entities import Patrimonio, PatrimonioAnexo
    assert hasattr(Patrimonio,'estado_conservacao')
    assert hasattr(Patrimonio,'vida_util_anos')
    assert hasattr(Patrimonio,'fornecedor_id')
    assert hasattr(PatrimonioAnexo,'conteudo')


def test_situacoes_com_inativo():
    from services.patrimonio import SITUACOES
    assert 'INATIVO' in SITUACOES and 'BAIXADO' in SITUACOES and 'OBSOLETO' in SITUACOES


def test_pagina_tem_campos_e_documentos():
    root=Path(__file__).resolve().parents[1]
    txt=(root/'pages/11_Patrimonio.py').read_text(encoding='utf-8')
    for termo in ['Nº Patrimonial','Estado de conservação','Vida útil (anos)','Documentos do bem','Nota Fiscal','Fornecedor','❓']:
        assert termo in txt
    assert 'DD/MM/YYYY' in txt


def test_fluxo_v265_preservado():
    root=Path(__file__).resolve().parents[1]
    txt=(root/'pages/10_Fluxo_de_Caixa.py').read_text(encoding='utf-8')
    assert 'Fluxo de Caixa' in txt
    assert 'Projetado' in txt or 'PROJETADO' in txt
