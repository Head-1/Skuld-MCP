#!/usr/bin/env python3
import socket
import json
import os
import uuid
import sys

def load_config():
    """Carrega o caminho do socket do config.json"""
    default_socket = "/data/data/com.termux/files/usr/tmp/skuld.sock"
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get("socket_path", default_socket)
        except Exception:
            return default_socket
    return default_socket

def send_command(cmd, params=None):
    socket_path = load_config()
    
    if not os.path.exists(socket_path):
        print(f"Erro: Socket não encontrado em {socket_path}")
        print("Certifique-se de que o skuld-core está rodando.")
        return None

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(socket_path)
        message = {
            "id": f"cli_{uuid.uuid4().hex[:8]}",
            "cmd": cmd,
            "agent": "skuld_cli_v1",
            "params": params or {}
        }
        client.send(json.dumps(message).encode())
        
        response = client.recv(4096)
        return json.loads(response.decode())
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        client.close()

def main():
    print("┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    print("┃           SKULD OS - CONTROL INTERFACE         ┃")
    print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
    print("  Pronto. Digite comandos como: ping, status, help\n")

    while True:
        try:
            user_input = input("[skuld] > ").strip()
            if not user_input: continue
            if user_input.lower() in ['exit', 'quit']: break

            # Separa comando de possíveis parâmetros JSON
            parts = user_input.split(' ', 1)
            cmd = parts[0]
            params = {}
            
            if len(parts) > 1:
                try:
                    params = json.loads(parts[1])
                except json.JSONDecodeError:
                    print("Erro: Parâmetros devem estar em formato JSON.")
                    continue

            resp = send_command(cmd, params)
            if resp:
                print(json.dumps(resp, indent=2))
        
        except KeyboardInterrupt:
            print("\nEncerrando CLI...")
            break

if __name__ == "__main__":
    main()
