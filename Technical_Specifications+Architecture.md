💀 Skuld MCP: Technical Specifications & Architecture
1. Visão Geral
O Skuld é um framework de automação "Mobile-First" que utiliza o 
Android (via Termux) como uma unidade de computação de borda 
(Edge Computing). 
Diferente de outras ferramentas de automação, o Skuld foca na 
Soberania Digital, eliminando intermediários na nuvem e 
utilizando protocolos de comunicação de baixa latência.
2. Pilares Arquiteturais
2.1 O Core (O Cérebro)
 * Linguagem: Go (Golang)
 * Comunicação: Unix Domain Sockets (UDS) - /tmp/skuld.sock
 * Persistência: SQLite3 para logs de intenção e estados.
 * Função: Atua como um orquestrador de mensagens. 
Ele recebe requisições de agentes, valida comandos, registra no 
banco de dados e despacha ações para o sistema operacional 
(via Termux-API).
2.2 O Bridge Agent (A Ponte)
 * Linguagem: Python / Flask
 * Protocolos: HTTP (REST), TCP/TLS e SSH Reverse Tunneling.
 * Função: Traduzir o mundo externo para a linguagem interna do 
Skuld. Ele permite que um servidor em Londres envie um comando 
para o seu celular no Brasil sem que você precise abrir portas 
no roteador, utilizando túneis SSH estáveis.
2.3 O CLI (A Interface Humana)
 * Linguagem: Python
 * Função: Uma interface de linha de comando interativa que 
permite ao usuário conversar diretamente com o Core, monitorar 
status e disparar notificações manualmente.
3. Fluxo de Dados (The Intent Path)
O ciclo de vida de uma ação no Skuld segue este fluxo:
 * Geração: Um evento ocorre 
(Ex: Pod do K8s cai ou Bateria do Celular atinge 15%).
 * Ingestão: O Agente correspondente formata um JSON e o envia 
para o Socket UDS.
 * Processamento: O Core recebe o JSON, gera um ID único, salva 
no SQLite e verifica se o comando existe.
 * Execução: O Core executa a tarefa (Ex: termux-notification).
 * Resposta: O resultado e a latência (em ms) são devolvidos ao 
agente e salvos no banco.
4. Segurança e Privacidade
 * Zero-Cloud: Nenhuma informação sai do dispositivo, a menos que 
o usuário configure explicitamente um agente de saída.
 * Auth Token: A Bridge HTTP utiliza autenticação via Token 
(Header Authorization) para evitar ataques de força bruta na 
rede local.
 * Socket Permissions: O UDS é configurado com permissões 
restritas ao usuário do Termux.
5. Capacidades de Integração Nativas
| Protocolo  | Uso no Skuld        | Exemplo de Aplicação               |
|------------|---------------------|------------------------------------|
| UDS        | Comunicação Interna | Agente de Bateria -> Core          |
| HTTP/REST  | Ingestão Externa    | Webhooks do GitHub / Prometheus    |
| SSH Tunnel | Acesso Remoto       | Controle do PC de casa via Celular |
| SQLite     | Auditoria           | Histórico de comandos e falhas     |
6. Roadmap de Desenvolvimento (v1.x)
 * [x] v1.0.0-rc1: Estabilização do Core em Go e Bridge Agent 
básico.
 * [ ] v1.1.0: Implementação de criptografia ponta-a-ponta nos 
túneis TCP.
 * [ ] v1.2.0: Dashboard Web minimalista rodando localmente via 
Agente Python.
 * [ ] v1.5.0: Sistema de plugins "Hot-Swap" 
(adicionar agentes sem reiniciar o Core).
7. Filosofia de Design: O Manifesto em Uma Frase
> "Se o seu celular é o dispositivo mais potente que você carrega, 
>ele deveria ser o seu servidor mais confiável."
 
