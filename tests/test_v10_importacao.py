from datetime import date
from decimal import Decimal
from database.db import init_db, session_scope
from services.seed import seed_initial_data
from services.tenancy import ensure_default_tesourarias, listar_tesourarias, set_active_tesouraria
from models.entities import Favorecido, ImportacaoExtrato
from services.financeiro import salvar_favorecido, criar_lancamento, listar_contas, listar_codigos
from services.importacao_extrato import criar_importacao, listar_itens, diagnosticar_duplicidade

def test_v10_competencia_pessoa_duplicidade():
    init_db()
    seed_initial_data(); ensure_default_tesourarias()
    central=next(x for x in listar_tesourarias(None, True) if x["codigo"]=="CENTRAL")
    set_active_tesouraria(central["id"])
    fid=salvar_favorecido("Pessoa Teste V10", "DOC-V10-2049", "COLABORADOR")
    with session_scope() as s:
        f=s.get(Favorecido,fid); assert f.codigo_cadastro.startswith("COL-")
    contas=listar_contas(); conta=next((x for x in contas if x['tipo']=='BANCO'),None)
    codigos=listar_codigos(); cod=codigos[0] if codigos else None
    assert conta and cod
    criar_lancamento(date(2048,12,15),cod['id'],'B','SAIDA','PAGAMENTO V10',Decimal('123.45'),conta['id'],'Pessoa Teste V10','DOCX','2048-12','APROVADO','TESTE',None,favorecido_id=fid)
    mov=[{'data':date(2048,12,15),'historico':'PAGAMENTO V10','favorecido':'Pessoa Teste V10','favorecido_id':fid,'documento':'DOCX','valor':Decimal('123.45'),'natureza':'SAIDA'}]
    iid=criar_importacao('extrato_v10.csv',b'v10',mov,None,'B','2048-12',conta['id'])
    with session_scope() as s:
        imp=s.get(ImportacaoExtrato,iid); assert imp.competencia=='2048-12'; assert imp.conta_financeira_id==conta['id']
    itens=listar_itens(iid); assert itens[0]['duplicidade'] in ('DUPLICADO_EXATO','POSSIVEL_DUPLICIDADE')
    diag,similar=diagnosticar_duplicidade(date(2048,12,15),Decimal('123.45'),cod['id'],'B','SAIDA','PAGAMENTO V10',fid,'Pessoa Teste V10','DOCX',conta['id'])
    assert diag=='DUPLICADO_EXATO' and similar
