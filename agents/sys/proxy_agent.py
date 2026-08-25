import socket
import select
import threading
import struct

# CONFIGURAÇÃO DE ACESSO (O que você vai vender)
PROXY_HOST = '0.0.0.0'
PROXY_PORT = 8080
USER = "admin"      # Mude para o seu usuário
PASS = "skuld123"   # Mude para sua senha

class SkuldProxy:
    def __init__(self):
        self.running = True

    def handle_client(self, connection):
        try:
            # 1. Handshake inicial SOCKS5
            version, nmethods = struct.unpack('!BB', connection.recv(2))
            methods = connection.recv(nmethods)
            
            # 2. Exigir Autenticação (Método 0x02)
            connection.sendall(struct.pack('!BB', 0x05, 0x02))
            
            # 3. Validar Usuário/Senha
            auth_data = connection.recv(512)
            ver = auth_data[0]
            ulen = auth_data[1]
            user = auth_data[2:2+ulen].decode()
            plen = auth_data[2+ulen]
            password = auth_data[3+ulen:3+ulen+plen].decode()
            
            if user == USER and password == PASS:
                connection.sendall(struct.pack('!BB', 0x01, 0x00)) # Sucesso
            else:
                connection.sendall(struct.pack('!BB', 0x01, 0x01)) # Falha
                return

            # 4. Receber pedido de conexão do cliente
            data = connection.recv(4)
            mode, addr_type = data[1], data[3]
            
            if addr_type == 1: # IPv4
                address = socket.inet_ntoa(connection.recv(4))
            elif addr_type == 3: # Domain name
                domain_len = connection.recv(1)[0]
                address = connection.recv(domain_len).decode()
            
            port = struct.unpack('!H', connection.recv(2))[0]

            # 5. Conectar ao destino final
            remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote.connect((address, port))
            bind_address = remote.getsockname()
            
            # Confirmar sucesso para o cliente
            resp = struct.pack('!BBBBIH', 0x05, 0x00, 0x00, 0x01, 0, 0)
            connection.sendall(resp)

            # 6. Transferência de dados bidirecional (Tunneling)
            self.exchange_data(connection, remote)
            
        except Exception as e:
            pass
        finally:
            connection.close()

    def exchange_data(self, client, remote):
        while self.running:
            r, w, e = select.select([client, remote], [], [])
            if client in r:
                data = client.recv(4096)
                if remote.send(data) <= 0: break
            if remote in r:
                data = remote.recv(4096)
                if client.send(data) <= 0: break

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((PROXY_HOST, PROXY_PORT))
        server.listen(10)
        print(f"[*] Skuld Proxy SOCKS5 ONLINE em {PROXY_PORT}")
        while self.running:
            conn, addr = server.accept()
            threading.Thread(target=self.handle_client, args=(conn,)).start()

if __name__ == "__main__":
    proxy = SkuldProxy()
    proxy.start()
