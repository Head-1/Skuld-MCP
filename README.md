# 📜 [Leia o Manifesto](MANIFESTO.md)

## 🌐 Language / Idioma
[English](#about-the-project) | [Português](#sobre-o-projeto)

---

### About the Project
**Skuld** is a lightweight, local-first automation framework designed to run on Android via Termux. It acts as a central nervous system for your digital infrastructure, allowing you to bridge cloud environments (like K3s/K8s), home automation, and system monitoring into a single, secure mobile interface.

**Key Features:**
* **Go-Powered Core:** High-performance Unix Domain Socket (UDS) server for inter-process communication.
* **Bridge Agent:** Built-in support for HTTP Webhooks and SSH Reverse Tunneling.
* **Extensible:** Write agents in any language (Python, Bash, JS) to talk to the Core.
* **Private by Design:** No cloud middleman. Your data, your rules.

---

### Sobre o Projeto
O **Skuld** é um framework de automação leve e local-first, projetado para rodar no Android via Termux. Ele atua como o sistema nervoso central para sua infraestrutura digital, permitindo conectar ambientes em nuvem (como K3s/K8s), automação residencial e monitoramento de sistemas em uma interface móvel única e segura.

**Recursos Principais:**
* **Core em Go:** Servidor de alta performance via Unix Domain Socket (UDS).
* **Agente de Ponte:** Suporte nativo para Webhooks HTTP e Túneis Reversos SSH.
* **Extensível:** Crie agentes em qualquer linguagem (Python, Bash, JS) para se comunicar com o Core.
* **Privacidade:** Sem intermediários na nuvem. Seus dados, suas regras.
* 

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
