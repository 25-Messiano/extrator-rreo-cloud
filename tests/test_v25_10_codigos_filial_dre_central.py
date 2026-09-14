from services.tenancy import ensure_default_tesourarias, criar_tesouraria, set_active_tesouraria
from services.financeiro import salvar_codigo, listar_codigos, salvar_grupo, configurar_codigos_grupo, auditoria_configuracao_dre

def test_codigos_sao_individuais_por_filial():
    ensure_default_tesourarias()
    a=criar_tesouraria("F-A","Filial A")
    b=criar_tesouraria("F-B","Filial B")
    set_active_tesouraria(a); ca=salvar_codigo("101","Codigo A",permite_saida=True)
    set_active_tesouraria(b); cb=salvar_codigo("101","Codigo B",permite_saida=True)
    assert ca != cb
    assert listar_codigos()[0]["descricao"]=="Codigo B"
    set_active_tesouraria(a)
    assert listar_codigos()[0]["descricao"]=="Codigo A"

def test_dre_global_mapeia_codigo_de_filial_especifica():
    a=criar_tesouraria("F-C","Filial C")
    set_active_tesouraria(a); cid=salvar_codigo("777","Codigo Local",permite_saida=True)
    gid=salvar_grupo("9.9","Grupo Oficial",ordem=999)
    configurar_codigos_grupo(gid,[cid],tesouraria_id=a)
    r=auditoria_configuracao_dre(a)
    assert r["codigos"][0]["grupo"]=="9.9"
