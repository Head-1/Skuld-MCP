# 📜 [Leia o Manifesto](MANIFESTO.md)

# 💀 SKULD MCP (Mobile Control Protocol)

O Skuld é um ecossistema de automação modular (MCP) que transforma o Android em um hub de controle para infraestrutura (K8s/K3s), IoT e monitoramento sistêmico.

## 📁 Estrutura de Diretórios
- `/bin`: Binários compilados (skuld-core).
- `/core`: Código-fonte em Go do servidor central.
- `/agents`: Agentes em Python (Bateria, Git, Monitoramento).
- `/data`: Banco de dados SQLite e persistência.
- `/logs`: Logs estruturados do sistema.

## ⚙️ Configuração
O Skuld utiliza um arquivo `config.json` na raiz para definir caminhos de execução:
```json
{
    "socket_path": "/caminho/para/skuld.sock",
    "data_dir": "/caminho/para/data",
    "log_file": "/caminho/para/logs/core.log",
    "version": "v1.0.0-rc1"
}


##By Headmaster.
