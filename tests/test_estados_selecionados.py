from core.politica_operacoes import Abrangencia, Fonte, criar_politica, politica_da_execucao


def test_abrangencia_estados_selecionados_existe():
    assert Abrangencia.ESTADOS_SELECIONADOS.value == "Estados selecionados"


def test_politica_rreo_estados_selecionados_isola_fonte():
    politica = politica_da_execucao("RREO — Estados selecionados")
    assert politica.fonte is Fonte.RREO
    assert politica.abrangencia is Abrangencia.ESTADOS_SELECIONADOS
    assert politica.usar_rreo is True
    assert politica.usar_fnde is False


def test_politica_combinada_estados_selecionados():
    politica = criar_politica(Fonte.COMBINADO, Abrangencia.ESTADOS_SELECIONADOS)
    assert politica.usar_rreo is True
    assert politica.usar_fnde is True
