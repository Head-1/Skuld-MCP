import socket
import json
import os
import threading
import subprocess
import time
import uuid
from flask import Flask, request, jsonify

# Configuração Global
CONFIG_PATH = os.path.expanduser("~/skuld/config.json")
UDS_PATH = ""
BRIDGE_CONFIG = {}

app = Flask(__name__)

# --- 1. Funções Auxiliares ---
def load_config():
    global UDS_PATH, BRIDGE_CONFIG
    try:
        with open(CONFIG_PATH, 'r') as f:
            cfg = json.load(f)
            UDS_PATH = cfg.get("socket_path", "")
            BRIDGE_CONFIG = cfg.get("bridge", {})
    except Exception as e:
        print(f"[ERR] Falha ao carregar config: {e}")

def send_to_core(cmd, params, agent_name="bridge_agent"):
    """Envia dados recebidos da rede para o Core via UDS"""
    if not os.path.exists(UDS_PATH):
        return {"error": "Core offline"}
    
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(UDS_PATH)
        msg = {
            "id": f"bridge_{uuid.uuid4().hex[:6]}",
            "cmd": cmd,
            "agent": agent_name,
            "params": params
        }
        client.send(json.dumps(msg).encode())
        resp = client.recv(4096)
        client.close()
        return json.loads(resp.decode())
    except Exception as e:
        return {"error": str(e)}

# --- 2. Servidor HTTP (REST API) ---
@app.route('/api/v1/event', methods=['POST'])
def receive_event():
    """Endpoint para Webhooks (K8s, Github, Scripts)"""
    # Verificação de Segurança
    token = request.headers.get("Authorization")
    if token != BRIDGE_CONFIG.get("auth_token"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    cmd = data.get("cmd", "notify_user") # Default para notificação
    params = data.get("params", {})
    
    # Repassa ao Core
    response = send_to_core(cmd, params, agent_name="http_bridge")
    return jsonify(response)

def run_http_server():
    port = BRIDGE_CONFIG.get("http_port", 5000)
    print(f"[BRIDGE] HTTP Server ouvindo na porta {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)

# --- 3. Gerenciador de Túnel SSH ---
def run_ssh_manager():
    """Mantém túneis SSH abertos para acesso remoto (Reverse Tunnel)"""
    tunnels = BRIDGE_CONFIG.get("ssh_tunnels", [])
    if not tunnels:
        print("[BRIDGE] Nenhum túnel SSH configurado.")
        return

    while True:
        for t in tunnels:
            # Ex: ssh -N -R 8080:localhost:5000 user@server
            remote_port = t.get("remote_port")
            local_port = t.get("local_port", BRIDGE_CONFIG.get("http_port", 5000))
            user_host = f"{t['user']}@{t['host']}"
            
            # Verifica se já está rodando
            check = subprocess.run(["pgrep", "-f", f"{remote_port}:localhost"], stdout=subprocess.PIPE)
            
            if check.returncode != 0:
                print(f"[BRIDGE] Iniciando túnel {t['name']} ({user_host})...")
                # -f coloca em background, -N não executa comando remoto, -R faz o túnel reverso
                cmd = f"ssh -f -N -R {remote_port}:localhost:{local_port} {user_host}"
                os.system(cmd)
        
        time.sleep(60) # Verifica a cada minuto

# --- 4. Main ---
if __name__ == "__main__":
    load_config()
    
    # Registra o agente no Core
    send_to_core("register_agent", {}, "bridge_main")

    # Inicia Threads
    t_http = threading.Thread(target=run_http_server)
    t_http.daemon = True
    t_http.start()

    t_ssh = threading.Thread(target=run_ssh_manager)
    t_ssh.daemon = True
    t_ssh.start()

    # Mantém o script rodando
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("[BRIDGE] Encerrando...")
