import socket
import json
import uuid
import sys
import os

# CAMINHO ABSOLUTO QUE O SEU LOG MOSTROU:
SOCKET_PATH = "/data/data/com.termux/files/home/skuld/skuld.sock"

def send_command(cmd, params=None):
    if not os.path.exists(SOCKET_PATH):
        return {"status": "error", "error": f"Socket nao encontrado em {SOCKET_PATH}"}

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(SOCKET_PATH)
            payload = {
                "id": f"cli_{uuid.uuid4().hex[:8]}",
                "cmd": cmd,
                "agent": "skuld_cli",
                "params": params or {}
            }
            client.sendall(json.dumps(payload).encode())
            response = client.recv(4096)
            return json.loads(response.decode())
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    print("\033[H\033[J", end="") 
    print("┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    print("┃           SKULD OS - CONTROL INTERFACE         ┃")
    print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
    
    resp = send_command("ping")
    if "error" in resp:
        print(f"Erro de conexão: {resp['error']}")
        sys.exit(1)

    print(f"  System: ONLINE | Latency: {resp.get('latency_ms', 0)}ms\n")

    while True:
        try:
            line = input("[skuld] > ").strip()
            if not line: continue
            if line in ["exit", "quit"]: break
            
            resp = send_command(line)
            print(json.dumps(resp, indent=2))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    main()
