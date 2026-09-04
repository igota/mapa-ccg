from flask import Flask, render_template, request, jsonify, redirect, stream_with_context, url_for, session
from flask import Response
from threading import Event
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import re
import sys
import tempfile
import time
import requests
from bs4 import BeautifulSoup
from threading import Timer
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

# Pasta onde está o .exe (build) ou o app.py (dev) — não depende do diretório de trabalho atual
_base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_base_dir, '.env'))


def env_bool(nome, padrao='True'):
    return os.environ.get(nome, padrao).strip().lower() in ('1', 'true', 'yes')


app = Flask(__name__)


def salvar_json_atomico(dados, caminho):
    dir_ = os.path.dirname(os.path.abspath(caminho))
    with tempfile.NamedTemporaryFile('w', dir=dir_, delete=False,
                                     suffix='.tmp', encoding='utf-8') as tmp:
        json.dump(dados, tmp, ensure_ascii=False, indent=4)
        tmp_path = tmp.name
    os.replace(tmp_path, caminho)


# Evento de atualização (aqui vamos usar um Event do threading para sinalizar a atualização)
atualizacao_evento = Event()
notificacao_evento = Event()
tabela_atual = "manha"  # Valor inicial padrão
app.secret_key = os.urandom(24)  # Necessária para gerenciar sessões
visualizacao_automatica = True # Variável global para armazenar o estado do checkbox

# Variável para armazenar o caminho do arquivo JSON
json_file_import = os.environ.get('JSON_FILE_IMPORT', 'importa_dados.json')
usuarios_file = os.environ.get('USUARIOS_FILE', 'usuarios.json')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """Renderiza a página inicial com os dados do arquivo JSON ou capturados."""
    dados = carregar_dados()
    return render_template('index.html', **dados)


# Função para carregar usuários do arquivo JSON
def carregar_usuarios():
    if os.path.exists(usuarios_file):
        with open(usuarios_file, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    return {}


# Função para salvar usuários no arquivo JSON
def salvar_usuarios(usuarios):
    with open(usuarios_file, 'w', encoding='utf-8') as file:
        json.dump(usuarios, file, indent=4, ensure_ascii=False)


# Função para atualizar o formato do JSON existente
def atualizar_formato_usuarios(usuarios):
    for login, dados in usuarios.items():
        # Se o formato for antigo (apenas senha como string), atualize
        if isinstance(dados, str):
            usuarios[login] = {
                "senha": dados,
                "permissao": "Colaborador"  # Permissão padrão
            }
    salvar_usuarios(usuarios)  # Salva o arquivo atualizado


@app.route('/login', methods=['POST'])
def login():
    """Processa o login."""
    login = request.form.get('login')
    senha = request.form.get('senha')
    usuarios = carregar_usuarios()

    # Atualiza o formato do JSON (se necessário)
    atualizar_formato_usuarios(usuarios)

    # Verifica se o login existe e a senha é válida
    if login in usuarios and check_password_hash(usuarios[login]['senha'], senha):
        session['usuario'] = login  # Armazena o usuário na sessão
        session['permissao'] = usuarios[login]['permissao']  # Armazena a permissão
        return redirect(url_for('pagina_edicao'))
    else:
        return render_template('index.html', error='Login ou senha inválidos.')


@app.route('/register', methods=['POST'])
@login_required 
def register():
    """Cadastra um novo usuário."""
    login = request.form.get('login')
    senha = request.form.get('senha')
    permissao = request.form.get('permissao')  # Captura a permissão
    usuarios = carregar_usuarios()

    if login in usuarios:
        return render_template('index.html', error='Usuário já existe.')
    else:
        # Gera o hash da senha antes de salvar
        senha_hash = generate_password_hash(senha)
        usuarios[login] = {
            "senha": senha_hash,
            "permissao": permissao or "Colaborador"  # Permissão padrão
        }
        salvar_usuarios(usuarios)
        return render_template('index.html', success='Usuário cadastrado com sucesso.')


@app.route('/pagina_edicao')
def pagina_edicao():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    permissao_usuario = session.get('permissao', 'Colaborador')
    print(f"Permissão do usuário logado: {permissao_usuario}")  # Verifique no terminal
    return render_template('paginaEdicao.html', permissao_usuario=permissao_usuario)


@app.route('/logout')
def logout():
    """Faz logout do usuário."""
    session.pop('usuario', None)
    return redirect(url_for('index'))        





@app.route('/atualizar_dados')

def atualizar_dados():
    """Força a captura de dados do sistema e salva em JSON."""
    try:
        # Captura os dados mais recentes
        novos_dados = captura_vitae()

        # Carrega os dados existentes do arquivo JSON, se existirem
        try:
            with open(json_file_import, 'r', encoding='utf-8') as json_file:
                dados_existentes = json.load(json_file)
        except FileNotFoundError:
            dados_existentes = {'dados_manha': [], 'dados_tarde': [], 'dados_noite': []}

        # Combina todos os prontuários existentes no JSON atual em um único conjunto
        prontuarios_existentes = {
            item['prontuario']
            for periodo in ['dados_manha', 'dados_tarde', 'dados_noite']
            for item in dados_existentes.get(periodo, [])
        }

        # Combina todos os prontuários capturados em um único conjunto
        prontuarios_capturados = {
            item['prontuario']
            for periodo in ['dados_manha', 'dados_tarde', 'dados_noite']
            for item in novos_dados.get(periodo, [])
        }

        # Inicializa os dados atualizados
        dados_atualizados = {}

        # Filtra os dados do JSON atual para manter apenas os prontuários presentes nos capturados
        for periodo in ['dados_manha', 'dados_tarde', 'dados_noite']:
            dados_atualizados[periodo] = [
                item for item in dados_existentes.get(periodo, [])
                if item['prontuario'] in prontuarios_capturados
            ]

        # Adiciona novos prontuários capturados que não estão no JSON atual
        for periodo in ['dados_manha', 'dados_tarde', 'dados_noite']:
            for item in novos_dados.get(periodo, []):
                if item['prontuario'] not in prontuarios_existentes:  # Verifica se o prontuário não está no JSON atual
                    dados_atualizados[periodo].append(item)

        # Adiciona os contadores de cada período
        dados_atualizados['cont_manha'] = len(dados_atualizados['dados_manha'])
        dados_atualizados['cont_tarde'] = len(dados_atualizados['dados_tarde'])
        dados_atualizados['cont_noite'] = len(dados_atualizados['dados_noite'])

        # Salva os dados atualizados no arquivo JSON
        salvar_json_atomico(dados_atualizados, json_file_import)

        # Retorna uma resposta JSON de sucesso
        return jsonify({
            'success': True,
            'message': 'Dados atualizados com sucesso'
        }), 200

    except Exception as e:
        # Retorna uma resposta JSON de erro
        return jsonify({
            'success': False,
            'message': f'Erro ao atualizar dados: {str(e)}'
        }), 500






def carregar_dados():
    """Carrega dados do arquivo JSON."""
    if os.path.exists(json_file_import):
        with open(json_file_import, 'r', encoding='utf-8') as json_file:
            try:
                return json.load(json_file)
            except json.JSONDecodeError:
                print("Erro ao ler o arquivo JSON. O arquivo pode estar corrompido.")
                return {}
    else:
        dados = captura_vitae()
        salvar_json_atomico(dados, json_file_import)
        return dados

_VITAE_URL = os.environ["VITAE_URL"]
_VITAE_UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/149.0.0.0 Safari/537.36")
_vitae_sess = None


def _get_vitae_sess():
    global _vitae_sess
    if _vitae_sess is None:
        _vitae_sess = requests.Session()
        _vitae_sess.headers["User-Agent"] = _VITAE_UA
    return _vitae_sess


def _vitae_login(sess):
    sess.get(f"{_VITAE_URL}/login.jsf")
    resp = sess.post(
        f"{_VITAE_URL}/login.jsf",
        data={
            "formulario":             "formulario",
            "login":                  os.environ["VITAE_LOGIN"],
            "xyb-ac":                 os.environ["VITAE_SENHA"],
            "formulario:botaoLogin":  "confirmar",
            "formulario:host":        os.environ["VITAE_HOST"],
            "javax.faces.ViewState":  "j_id1",
        },
        allow_redirects=True,
    )
    if "paginaPrincipal.jsf" not in resp.url:
        raise Exception("Login no mapa cirúrgico falhou")
    print("Login mapa OK")


def captura_vitae():
    """Captura o mapa cirúrgico via HTTP (requests + BeautifulSoup)."""
    sess = _get_vitae_sess()

    # Verifica se a sessão ainda é válida; refaz login se necessário
    check = sess.get(f"{_VITAE_URL}/paginaPrincipal.jsf", allow_redirects=True)
    if "login.jsf" in check.url:
        _vitae_login(sess)

    # Extrai o ViewState atual de paginaPrincipal
    pp_soup = BeautifulSoup(
        sess.get(f"{_VITAE_URL}/paginaPrincipal.jsf").text, "html.parser"
    )
    vs_pp = pp_soup.find("input", {"name": "javax.faces.ViewState"})["value"]

    # AJAX do menu "Cirúrgico" — retorna novo ViewState
    ajax = sess.post(
        f"{_VITAE_URL}/paginaPrincipal.jsf",
        data={
            "AJAXREQUEST":             "_viewRoot",
            "formCabecalho":           "formCabecalho",
            "javax.faces.ViewState":   vs_pp,
            "formCabecalho:j_id138":   "formCabecalho:j_id138",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    vs_mapa = BeautifulSoup(ajax.text, "html.parser").find(
        "input", {"name": "javax.faces.ViewState"}
    )["value"]

    # POST em cs_mapascirurgia.jsf com o ViewState retornado pelo AJAX
    resp = sess.post(
        f"{_VITAE_URL}/cs_mapascirurgia.jsf",
        data={
            "formularioMapas":        "formularioMapas",
            "javax.faces.ViewState":  vs_mapa,
        },
    )
    soup = BeautifulSoup(resp.text, "html.parser")

    # Os 3 tbodies de período: tblMapa:0:j_id<N>:tb ordenados por N → manhã/tarde/noite
    tbodies = sorted(
        soup.find_all("tbody", id=lambda x: x and re.search(r"tblMapa:0:j_id\d+:tb$", x)),
        key=lambda tb: int(re.search(r"j_id(\d+)", tb["id"]).group(1)),
    )

    def processar_tbody(tbody, periodo):
        dados = []
        if not tbody:
            return dados
        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 9 or not tr.get_text(strip=True):
                continue
            try:
                link = cells[0].find("a")
                dado = {
                    "prontuario":    link.get_text(strip=True) if link else cells[0].get_text(strip=True),
                    "paciente":      cells[1].get_text(strip=True),
                    "horario":       cells[3].get_text(strip=True),
                    "sala":          cells[4].get_text(strip=True),
                    "localizacao":   cells[5].get_text(strip=True),
                    "procedimento":  cells[7].get_text(separator="\n", strip=True),
                    "cirurgiao":     cells[8].get_text(strip=True),
                    "equipe":        "",
                    "enfermeiro":    "",
                    "p":             "",
                    "status":        "",
                    "especialidade": "",
                }
                dados.append(dado)
                print(f"  {periodo}: {dado['paciente'][:40]}")
            except Exception as e:
                print(f"  Erro linha ({periodo}): {e}")
        return dados

    dados_manha = processar_tbody(tbodies[0] if len(tbodies) > 0 else None, "manhã")
    dados_tarde = processar_tbody(tbodies[1] if len(tbodies) > 1 else None, "tarde")
    dados_noite = processar_tbody(tbodies[2] if len(tbodies) > 2 else None, "noite")

    print(f"Captura OK — Manhã:{len(dados_manha)} Tarde:{len(dados_tarde)} Noite:{len(dados_noite)}")

    return {
        "dados_manha": dados_manha,
        "dados_tarde": dados_tarde,
        "dados_noite": dados_noite,
        "cont_manha":  len(dados_manha),
        "cont_tarde":  len(dados_tarde),
        "cont_noite":  len(dados_noite),
    }


@app.route('/dados_manha')

def dados_manha():
    """Retorna os dados da Manhã do arquivo JSON."""
    dados = carregar_dados()
    return jsonify(dados['dados_manha'])

@app.route('/dados_tarde')

def dados_tarde():
    """Retorna os dados da Tarde do arquivo JSON."""
    dados = carregar_dados()
    return jsonify(dados['dados_tarde'])

@app.route('/dados_noite')

def dados_noite():
    """Retorna os dados da Noite do arquivo JSON."""
    dados = carregar_dados()
    return jsonify(dados['dados_noite'])

@app.route('/buscar_informacoes', methods=['POST'])

def buscar_informacoes():
    """Busca informações específicas no JSON com base no índice e período fornecidos."""
    dados_recebidos = request.get_json()
    index = dados_recebidos.get('index')
    periodo = dados_recebidos.get('periodo')

    # Carrega os dados do JSON
    dados = carregar_dados()

    # Determina a lista de dados com base no período
    if periodo == 'manha':
        dados_periodo = dados.get('dados_manha', [])
    elif periodo == 'tarde':
        dados_periodo = dados.get('dados_tarde', [])
    elif periodo == 'noite':
        dados_periodo = dados.get('dados_noite', [])
    else:
        return jsonify({
            'prontuario': 'Período inválido',
            'paciente': 'Período inválido',
            'localizacao': 'Período inválido',
            'cirurgiao': 'Período inválido',
        })

    # Verifica se o índice está dentro do intervalo de dados do período
    if 0 <= index < len(dados_periodo):
        item = dados_periodo[index]
        return jsonify({
            'prontuario': item['prontuario'],
            'paciente': item['paciente'],
            'localizacao': item['localizacao'],
            'cirurgiao': item['cirurgiao']
        })
    else:
        # Caso o índice não seja válido
        return jsonify({
            'prontuario': 'Não encontrado',
            'paciente': 'Não encontrado',
            'localizacao': 'Não encontrado',
            'cirurgiao': 'Não encontrado',
        })








@app.route('/salvar_dados', methods=['POST'])

def salvar_dados():
    try:
        # Recebe os dados do front-end
        dados = request.json
        
        # Limpar os dados antigos (substituindo todo o conteúdo)
        salvar_json_atomico(dados, json_file_import)

        return jsonify({"status": "success", "message": "Dados salvos com sucesso!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    


@app.route('/mapa')
def mapa():
    """Renderiza a página de mapa com os dados."""
    dados = carregar_dados()  # Carrega os dados do JSON
    return render_template('paginaMapa.html', **dados)

    
# Endpoint que o botão de "Atualizar Mapa" aciona
@app.route('/atualizar-mapa', methods=['POST'])

def atualizar_mapa():
    # Aciona o evento de atualização para a página do mapa
    atualizacao_evento.set()  # Notifica que há uma atualização para ser feita
    return jsonify(status='success')

@app.route('/evento-atualizacao-mapa')
def evento_atualizacao_mapa():
    def generate():
        while True:
            atualizacao_evento.wait()  # Espera até que o evento seja acionado
            
            # Carrega os dados diretamente, sem chamar as rotas
            dados = carregar_dados()
            dados_mapa = {
                'manha': dados.get('dados_manha', []),
                'tarde': dados.get('dados_tarde', []),
                'noite': dados.get('dados_noite', []),
                'cont_manha': dados.get('cont_manha', 0),
                'cont_tarde': dados.get('cont_tarde', 0),
                'cont_noite': dados.get('cont_noite', 0)
            }
            
            # Envia os dados atualizados como string JSON
            yield f"data: {json.dumps(dados_mapa)}\n\n"
            atualizacao_evento.clear()  # Reseta o evento após enviar a notificação

    return Response(stream_with_context(generate()), content_type='text/event-stream')

# --- Determina o turno atual com base na hora ---
def determinar_turno():
    hora = datetime.now().hour
    if 7 <= hora < 13:
        return "manha"
    elif 13 <= hora <= 19:
        return "tarde"
    else:
        return "noite"


@app.route('/obter_tabela_atual', methods=['GET'])
def obter_tabela_atual():
    global tabela_atual
    turno = determinar_turno()
    tabela_atual = turno
    
    # Retorna os dados COMPLETOS igual à rota dados-iniciais-mapa
    dados_mapa = {
        'manha': dados_manha().json,  # Dados completos da manhã
        'tarde': dados_tarde().json,  # Dados completos da tarde
        'noite': dados_noite().json,  # Dados completos da noite
        'turno_atual': turno          # Turno atual como informação adicional
    }
    
    return jsonify(dados_mapa)


# --- Agenda a próxima mudança automática de turno ---
def agendar_proxima_mudanca():
    global tabela_atual, visualizacao_automatica

    if not visualizacao_automatica:
        print("⏸️ Visualização automática desativada — não será agendada nova troca.")
        return

    turno_atual = determinar_turno()
    agora = datetime.now()

    # Define o próximo horário de mudança
    if turno_atual == "manha":
        proxima = agora.replace(hour=13, minute=0, second=0, microsecond=0)
    elif turno_atual == "tarde":
        proxima = agora.replace(hour=19, minute=0, second=0, microsecond=0)
    else:  # noite
        # CORREÇÃO: Verifica se 07:00 do mesmo dia já passou
        sete_hoje = agora.replace(hour=7, minute=0, second=0, microsecond=0)
        if agora < sete_hoje:
            # Ainda não são 07:00 hoje → usa 07:00 do mesmo dia
            proxima = sete_hoje
        else:
            # Já passou das 07:00 hoje → usa 07:00 do próximo dia
            proxima = (agora + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)

    # Garante que o horário é sempre futuro
    if proxima <= agora:
        # CORREÇÃO: Se ainda assim o horário não for futuro, adiciona tempo baseado no turno
        if turno_atual == "manha":
            proxima += timedelta(hours=1)  # próxima hora
        elif turno_atual == "tarde":
            proxima += timedelta(hours=1)
        else:  # noite
            proxima += timedelta(hours=1)

    segundos = (proxima - agora).total_seconds()
    print(f"🕒 Turno atual: {turno_atual} | Próxima troca em {segundos/60:.1f} minutos.")
    Timer(segundos, mudar_turno_automaticamente).start()


# --- Função que troca o turno automaticamente ---
def mudar_turno_automaticamente():
    global tabela_atual
    tabela_atual = determinar_turno()
    print(f"🔄 Mudança automática: turno agora é {tabela_atual}")
    notificacao_evento.set()
    agendar_proxima_mudanca()  # agenda a próxima troca


# --- SSE: envia eventos de mudança de turno ao mapa ---
@app.route('/event-stream')
def event_stream():
    def gerar():
        while True:
            notificacao_evento.wait()
            notificacao_evento.clear()
            yield f"data: {tabela_atual}\n\n"  # ⚠️ corrigido para enviar apenas o nome, como o JS espera
    return Response(gerar(), mimetype='text/event-stream')


# --- Rota para controlar a visualização (manual ou automática) ---
@app.route('/controlar_visualizacao', methods=['POST'])
@login_required 
def controlar_visualizacao():
    global tabela_atual, visualizacao_automatica
    data = request.json or {}
    
    print("📋 Dados recebidos:", data)  # Para debug
    
    # Controle do modo automático
    if "visualizacaoAutomatica" in data:
        visualizacao_automatica = data["visualizacaoAutomatica"]
        print("🧭 Visualização automática:", "Ativa" if visualizacao_automatica else "Desativada")
        
        # Se veio com tabela, atualiza também
        if "tabela" in data:
            tabela_atual = data["tabela"]
            print(f"📋 Tabela atualizada para: {tabela_atual}")
            notificacao_evento.set()
        
        if visualizacao_automatica:
            agendar_proxima_mudanca()
        return '', 204
    
    # Controle manual de troca de tabela
    if "tabela" in data:
        tabela_atual = data["tabela"]
        notificacao_evento.set()
        print(f"📋 Mapa alterado manualmente para: {tabela_atual}")
        return '', 204
    
    return '', 400


# --- Rotas auxiliares ---
@app.route('/turno-atual')
def turno_atual():
    global tabela_atual
    tabela_atual = determinar_turno()
    return jsonify({"turno": tabela_atual})



@app.route('/time', methods=['GET'])
def get_server_time():
    # Obtém a data e hora atual do servidor
    now = datetime.now()
    # Retorna a data no formato ISO
    return jsonify({"currentTime": now.isoformat()})


# --- INICIALIZAÇÃO DO SISTEMA --- 
def inicializar_sistema():
    global tabela_atual, visualizacao_automatica
    tabela_atual = determinar_turno()
    visualizacao_automatica = True
    
    print(f"🎯 Sistema de turnos inicializado | Turno: {tabela_atual} | Modo automático: {visualizacao_automatica}")
    
    # Agenda a primeira mudança automática
    agendar_proxima_mudanca()

# Chama a inicialização quando o módulo é importado
inicializar_sistema()


if __name__ == "__main__":
    app.run(debug=env_bool('FLASK_DEBUG'))