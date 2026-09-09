from pathlib import Path

from openpyxl import load_workbook

from modules.rreo import extract_text, extract_codes, verify_values, identify_internal_municipality
from modules.rreo_safe import extract_codes_geometry, identity_guard, sha256_file, result_fingerprint
from modules.mapeamento_nova_planilha import (
    obter_aba_destino,
    preencher_rreo_nova_planilha,
    verificar_resultados_gravados,
    verificar_resultados_em_arquivo,
)

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / 'data' / 'referencias_rreo' / 'RREO_Municipal_2025_Angelandia-MG.pdf'
BASE = ROOT / 'data' / 'RREO-TCM+FNDE PLANILHA BASE.xlsx'
CODES = ['1.1','1.2','1.3','1.4','2.1','2.1.1','2.1.2','2.2','2.3','2.4','2.5','2.6','6.1.1','6.2','6.2.1']


def test_geometry_reader_targets_b_column():
    values = extract_codes_geometry(PDF, CODES)
    assert values['1.1'] == 41626.32
    assert values['1.2'] == 77093.78
    assert values['2.2'] == 6399354.90
    assert values['6.1.1'] == 7603067.48


def test_independent_readers_agree_on_reference():
    text = extract_text(PDF)
    primary = extract_codes(text, CODES)
    checked = verify_values(PDF, primary, CODES)
    assert checked['ok'] is True
    assert checked['divergences'] == {}
    assert len(checked['pdf_sha256']) == 64
    assert 'PYMUPDF_GEOMETRY' in checked['method']


def test_identity_guard_blocks_wrong_city():
    assert identity_guard('Angelândia', 'Angelândia')['ok'] is True
    assert identity_guard('Angelândia', 'Divinópolis')['ok'] is False
    assert identity_guard('Angelândia', None, require_internal=True)['ok'] is False


def test_hash_and_result_fingerprint_are_deterministic():
    h1 = sha256_file(PDF)
    h2 = sha256_file(PDF)
    assert h1 == h2 and len(h1) == 64
    fp1 = result_fingerprint('3102852', 2025, 6, {'1.1': 41626.32})
    fp2 = result_fingerprint('3102852', 2025, 6, {'1.1': 41626.32})
    assert fp1 == fp2 and len(fp1) == 64


def test_post_write_and_post_xlsx_guard(tmp_path):
    out = tmp_path / 'safe.xlsx'
    out.write_bytes(BASE.read_bytes())
    wb = load_workbook(out)
    ws = obter_aba_destino(wb)
    # linha 1613 é a linha usada no teste técnico histórico de Angelândia
    values = {'1.1': 41626.32, '1.2': 77093.78, '2.2': 6399354.90}
    count = preencher_rreo_nova_planilha(ws, 1613, values)
    assert count == 3
    immediate = verificar_resultados_gravados(ws, 1613, values)
    assert immediate['ok'] is True
    wb.save(out)
    wb.close()
    persisted = verificar_resultados_em_arquivo(out, [{'row':1613,'ibge':'3102852','values':values}])
    assert persisted['ok'] is True
    assert persisted['total'] == 3


def _cities(uf, *names):
    return [
        {"codigo_ibge": f"{i+1:07d}", "nome": name, "uf": uf}
        for i, name in enumerate(names)
    ]


def test_v137_header_identity_never_uses_short_substring():
    cities = _cities("SC", "Itá", "Itajaí", "Ituporanga")
    city, conf, method, _, _ = identify_internal_municipality(
        "RELATORIO RREO\nITAJAI - SC\nRECEITAS REALIZADAS", cities, "SC", False
    )
    assert city and city["nome"] == "Itajaí"
    assert conf == 1.0
    assert method == "CABECALHO_EXATO_OU_ALIAS_CONTROLADO"


def test_v137_d_oeste_contraction_is_exact_but_not_shorter_city():
    cities = _cities("PR", "Tapejara", "Itapejara d'Oeste", "Pérola", "Pérola d'Oeste")
    city, *_ = identify_internal_municipality("ITAPEJARA DOESTE - PR\nPREVISAO", cities, "PR", False)
    assert city and city["nome"] == "Itapejara d'Oeste"
    city, *_ = identify_internal_municipality("PEROLA DOESTE - PR\nPREVISAO", cities, "PR", False)
    assert city and city["nome"] == "Pérola d'Oeste"


def test_v137_controlled_historical_aliases_rn():
    cities = _cities("RN", "Boa Saúde", "Campo Grande", "Arez", "Assú")
    cases = {
        "JANUARIO CICCO - RN": "Boa Saúde",
        "AUGUSTO SEVERO - RN": "Campo Grande",
        "ARES - RN": "Arez",
        "ACU - RN": "Assú",
    }
    for header, expected in cases.items():
        city, conf, method, _, _ = identify_internal_municipality(header, cities, "RN", False)
        assert city and city["nome"] == expected
        assert conf == 1.0
        assert method == "CABECALHO_EXATO_OU_ALIAS_CONTROLADO"


def test_v137_unknown_similar_name_stays_blocked():
    cities = _cities("SP", "Flores", "Floresta")
    city, conf, method, _, _ = identify_internal_municipality("FLORESTINHA - SP", cities, "SP", False)
    assert city is None
    assert conf == 0.0
    assert method == "MUNICIPIO_INTERNO_NAO_IDENTIFICADO"


def test_v137_identity_guard_accepts_safe_contraction_only():
    assert identity_guard("São Jorge d'Oeste", "SAO JORGE DOESTE")["ok"] is True
    assert identity_guard("Itapejara d'Oeste", "Tapejara")["ok"] is False


def test_v137_state_completeness_detects_missing_pdf():
    from modules.rreo_safe import validate_state_completeness
    result = validate_state_completeness(["Alpha", "Beta", "Gamma"], ["Alpha", "Gamma"])
    assert result["ok"] is False
    assert result["missing"] == ["Beta"]
    assert result["expected"] == 3
    assert result["found"] == 2


def test_v137_apostrophe_and_hyphen_canonicalization():
    from modules.rreo_safe import canonical_municipality_name
    assert canonical_municipality_name("Olho d'Água do Borges") == canonical_municipality_name("OLHO-DÁGUA DO BORGES")
    assert canonical_municipality_name("Tanque d'Arca") == canonical_municipality_name("TANQUE DARCA")
    assert canonical_municipality_name("Alta Floresta d'Oeste") == canonical_municipality_name("ALTA FLORESTA DOESTE")
