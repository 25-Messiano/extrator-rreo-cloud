from io import BytesIO

import pdfplumber

from core.relatorios_cloud_pdf import LinhaInventarioCloud, gerar_pdf_inventario, resumir_inventario


def test_resumo_inventario_cloud():
    linhas = [
        LinhaInventarioCloud('Araci', 'BA', True, False),
        LinhaInventarioCloud('Teofilandia', 'BA', True, True),
        LinhaInventarioCloud('Tucano', 'BA', False, True),
        LinhaInventarioCloud('Outro', 'BA', False, False),
    ]
    resumo = resumir_inventario(linhas)
    assert resumo.municipios == 4
    assert resumo.com_rreo == 2
    assert resumo.com_fnde == 2
    assert resumo.com_ambos == 1
    assert resumo.somente_rreo == 1
    assert resumo.somente_fnde == 1
    assert resumo.sem_arquivos == 1


def test_pdf_tem_colunas_e_status():
    linhas = [
        LinhaInventarioCloud('Araci', 'BA', True, False),
        LinhaInventarioCloud('Teofilandia', 'BA', True, True),
        LinhaInventarioCloud('Tucano', 'BA', False, True),
    ]
    pdf = gerar_pdf_inventario(linhas, 2025, 'Bahia (BA)')
    assert pdf.startswith(b'%PDF-')
    with pdfplumber.open(BytesIO(pdf)) as doc:
        texto = '\n'.join(page.extract_text() or '' for page in doc.pages)
    assert 'CIDADE' in texto
    assert 'ESTADO' in texto
    assert 'RREO' in texto
    assert 'FNDE' in texto
    assert 'Araci' in texto
    assert 'SIM' in texto
    assert ('NÃO' in texto) or ('NAO' in texto)
