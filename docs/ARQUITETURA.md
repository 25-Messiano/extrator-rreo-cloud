# Arquitetura interna

- `app.py`: rotas Flask e APIs.
- `config/storage.py`: configuração central das fontes do Cloud.
- `integrations/google_storage.py`: autenticação e download GCS.
- `modules/calendar_parser.py`: parser literal das datas oficiais.
- `modules/database/`: SQLite e consultas.
- `modules/web_search.py`: pesquisa externa opcional.
- `scripts/importar_calendario.py`: build do banco local.
- `scripts/validate_project.py`: validação estrutural/sintática.
- `templates/index.html`: interface SPA.
- `static/css/app.css`: visual responsivo.
- `static/js/app.js`: calendário, configurações, navegação e pesquisa.

A interface nunca recebe os caminhos técnicos das fontes do Cloud.

## Relatórios

- `modules/reports.py`: composição e geração dos PDFs com ReportLab.
- `POST /api/relatorios/pdf`: endpoint de geração e download.
- A página `Relatórios` no frontend coleta somente parâmetros de apresentação/recorte.
- O gerador consulta `modules/database/consultas.py`, portanto compartilha exatamente a mesma camada de dados da interface.
- Não existe conversão G <-> M paralela no gerador PDF.
- Intervalos são limitados para proteção de memória, CPU e tempo de resposta do Render.
