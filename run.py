import os
import sys
import tkinter as tk
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import threading
from waitress import serve
from app import app, determinar_turno, agendar_proxima_mudanca, env_bool
import subprocess
import webbrowser
import time

# Variável global para controle do servidor e processo de logs
server_running = True
log_process = None

# Configurações do servidor (lidas do .env, com fallback para os valores padrão)
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 5000))
THREADS = int(os.environ.get('THREADS', 100))
FLASK_DEBUG = env_bool('FLASK_DEBUG')

# Cria um ícone a partir de uma imagem
def create_image():
    image_paths = [
        p for p in [
            os.environ.get('ICON_PATH'),
            os.path.join(os.path.dirname(__file__), 'static', 'img', 'icone_map.ico')
        ] if p
    ]

    for path in image_paths:
        if os.path.exists(path):
            try:
                image = Image.open(path)
                image = image.resize((64, 64))
                return image
            except:
                continue
    
    # Ícone padrão se não encontrar
    image = Image.new('RGB', (64, 64), color='#2c3e50')
    draw = ImageDraw.Draw(image)
    draw.text((15, 25), "Mapa", fill='white')
    return image

# Função para parar o servidor
def stop_server():
    global server_running
    server_running = False
    print("🛑 Parando servidor...")

# 🔥 Função chamada ao clicar no ícone (clique único)
def on_click(icon, item):
    """Abre o navegador ao clicar no ícone"""
    webbrowser.open(f"http://127.0.0.1:{PORT}")

# Função para abrir o navegador (usada no menu)
def open_browser():
    webbrowser.open(f"http://127.0.0.1:{PORT}")

# Mostra uma janela com informações do sistema
def show_about():
    root = tk.Tk()
    root.title("Sobre - Mapa CCG")
    root.geometry("450x350")
    root.resizable(False, False)
    root.eval('tk::PlaceWindow . center')
    
    frame = tk.Frame(root, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Título
    tk.Label(frame, text="Mapa CCG", font=("Arial", 16, "bold"), fg="#2c3e50").pack(pady=(0, 10))
    
    # Informações
    info_text = """
    Sistema de Mapa de Leitos - CCG
    
    Versão: 1.0
    Desenvolvido por: Igor Maciel de Sousa
    
    Funcionalidades:
    • Mapa de ocupação de leitos
    • Atualização automática por turno
    • Exportação de relatórios
    • Visualização em tempo real
    
    ISGH - INSTITUTO DE SAÚDE E GESTÃO HOSPITALAR
    """
    
    tk.Label(frame, text=info_text, justify=tk.LEFT, font=("Arial", 10)).pack()
    
    # Status do servidor
    status_frame = tk.Frame(frame)
    status_frame.pack(pady=(15, 0))
    tk.Label(status_frame, text="Status: ", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    tk.Label(status_frame, text="🟢 Online", font=("Arial", 10), fg="green").pack(side=tk.LEFT)
    
    # Botão Fechar
    tk.Button(frame, text="Fechar", command=root.destroy, bg="#2c3e50", fg="white", 
              padx=20, pady=5, cursor="hand2").pack(pady=(20, 0))
    
    root.mainloop()

# Função para mostrar logs (console)
def show_logs():
    global log_process
    if log_process is None or log_process.poll() is not None:
        print("📟 Abrindo console de logs...")
        log_process = subprocess.Popen([sys.executable, "-u", "app.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)

# Ação para sair
def quit_action(icon, item):
    print("🔴 Saindo do aplicativo...")
    icon.stop()
    stop_server()
    if log_process:
        log_process.terminate()
    time.sleep(1)
    os._exit(0)

# Função principal do ícone de bandeja
def setup_tray_icon():
    try:
        icon = Icon("MapaCCG")
        icon.icon = create_image()
        icon.title = "Mapa CCG - Mapa de Leitos"
        
        # 🔥 Configurar callback do clique
        icon.on_click = on_click
        
        # Menu do ícone
        icon.menu = Menu(
            MenuItem("Abrir no Navegador (Clique aqui)", lambda icon, item: open_browser()),
            MenuItem("Sobre", lambda icon, item: show_about()),
            MenuItem("Abrir Console de Logs", lambda icon, item: show_logs()),
            MenuItem("Sair", quit_action)
        )
        
        icon.run()
    except Exception as e:
        print(f"❌ Erro no tray icon: {e}")

# Função para iniciar o servidor Waitress
def run_server():
    print("="*60)
    print(" MAPA CCG - SISTEMA DE MAPA DE LEITOS ")
    print("="*60)
    print(f" 🌐 Servidor: http://{HOST}:{PORT}")
    print(f" 📁 Servindo aplicação com Waitress ({THREADS} threads)")
    print("="*60)
    print()
    
    while server_running:
        try:
            serve(app, host=HOST, port=PORT, threads=THREADS)
        except Exception as e:
            if server_running:
                print(f"❌ Erro no servidor: {e}")
                time.sleep(2)

# Função para iniciar com console (debug)
def run_with_console():
    print("="*60)
    print(" MAPA CCG - SISTEMA DE MAPA DE LEITOS ")
    print("="*60)
    print(f" 🌐 Servidor: http://{HOST}:{PORT}")
    print(" 🔧 Modo: Console (debug ativo)")
    print("="*60)
    print()
    
    app.run(debug=FLASK_DEBUG, host=HOST, port=PORT, threaded=True)

if __name__ == "__main__":
    import sys
    
    # Verificar se deve rodar com console ou com bandeja
    if len(sys.argv) > 1 and sys.argv[1] == '--console':
        # Modo console (para debug)
        run_with_console()
    else:
        # Modo bandeja (para produção)
        print("🔧 Iniciando Mapa CCG em modo bandeja...")
        print("   💡 Dica: Clique no ícone para abrir o navegador")
        print("   🔄 Clique com botão direito para menu de opções")
        print()
        

        
        # Inicia o ícone da bandeja em uma thread separada
        tray_thread = threading.Thread(target=setup_tray_icon, daemon=True)
        tray_thread.start()
        
        # Pequena pausa para garantir que o ícone foi criado
        time.sleep(1)
        
        # Inicia o servidor Flask com waitress em outra thread
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        print(f"✅ Servidor iniciado em http://{HOST}:{PORT}")
        print("📌 Ícone na bandeja do sistema")
        print("   • Clique no ícone: Abre no navegador")
        print("   • Clique direito: Menu de opções")
        print("   • Para encerrar: Clique em 'Sair' no menu")
        print()
        
        # Mantém o programa principal ativo
        try:
            while server_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Interrompido pelo usuário")
            stop_server()
        finally:
            print("👋 Encerrando aplicação...")