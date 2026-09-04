# Mapa CCG

Sistema de Mapa de Leitos do Centro Cirúrgico (CCG), desenvolvido para o **ISGH – Instituto de Saúde e Gestão Hospitalar**.

A aplicação captura o mapa cirúrgico diretamente do sistema **Vitae** (via scraping HTTP autenticado), organiza os procedimentos por turno (manhã, tarde e noite) e exibe um painel em tempo real com os leitos/salas, pacientes, cirurgiões e status de cada cirurgia — permitindo também edição manual dos dados exibidos.

## Funcionalidades

- Login de usuários com senha criptografada (`werkzeug.security`) e níveis de permissão (Administrador / Colaborador).
- Captura automática do mapa cirúrgico do sistema Vitae e importação incremental dos dados (mantém edições manuais e remove prontuários que saíram do Vitae).
- Painel de visualização (`/mapa`) com atualização em tempo real via Server-Sent Events (SSE).
- Troca automática de turno (manhã/tarde/noite) com base no horário, com opção de controle manual.
- Página de edição (`/pagina_edicao`) para ajustar equipe, enfermeiro e status das cirurgias.
- Empacotamento como aplicativo Windows (ícone na bandeja do sistema) via PyInstaller.

## Stack

- **Backend:** Python, Flask, Waitress (servidor WSGI de produção)
- **Scraping:** requests + BeautifulSoup (autenticação e parsing do sistema Vitae/JSF)
- **Frontend:** HTML/CSS/JS (templates Jinja2, sem framework SPA)
- **Empacotamento:** PyInstaller (`run.spec`) + pystray (ícone de bandeja)

## Estrutura do projeto

```
app.py              # Aplicação Flask: rotas, login, captura e persistência dos dados
run.py              # Ponto de entrada para produção (bandeja do sistema + Waitress)
run.spec            # Spec do PyInstaller para gerar o executável
templates/          # Páginas HTML (login, edição, mapa)
static/             # CSS, JS e imagens
data/               # Dados em runtime (não versionado — ver abaixo)
```

## Configuração

As configurações ficam em um arquivo `.env` na raiz do projeto (não versionado). Use `.env.example` como base:

```bash
cp .env.example .env
```

| Variável | Descrição |
|---|---|
| `VITAE_URL` | URL base do sistema Vitae de onde o mapa cirúrgico é capturado |
| `VITAE_HOST` | Host/porta enviado no login do Vitae |
| `VITAE_LOGIN` / `VITAE_SENHA` | Credenciais de acesso ao Vitae |
| `HOST` / `PORT` / `THREADS` | Configuração do servidor Waitress |
| `FLASK_DEBUG` | Ativa modo debug do Flask (`True`/`False`) |
| `ICON_PATH` | Caminho do ícone exibido na bandeja do sistema (build) |
| `JSON_FILE_IMPORT` | Caminho do JSON com os dados do mapa cirúrgico |
| `USUARIOS_FILE` | Caminho do JSON com os usuários do sistema |

## Executando em desenvolvimento

```bash
pip install -r requirements.txt
python app.py
```

Ou, para simular o modo produção com console:

```bash
python run.py --console
```

Para gerar o executável (PyInstaller):

```bash
pip install -r requirements-build.txt
pyinstaller run.spec
```

## Dados e privacidade

Este sistema lida com **dados reais de pacientes e prontuários hospitalares**, além de credenciais de acesso a sistemas internos. Por isso:

- Os arquivos em `data/` (`usuarios.json`, `importa_dados.json`) e o `.env` **nunca devem ser versionados** — estão listados no `.gitignore`.
- Pastas de build (`dist/`, `build/`) também são ignoradas, pois embutem esses dados no executável gerado.
- Ao clonar o repositório, esses arquivos precisam ser recriados/fornecidos localmente para o sistema funcionar.
