#!/data/data/com.termux/files/usr/bin/bash
echo "🚀 Iniciando Infraestrutura Skuld no Android..."

# 1. Garante que a CPU não vai dormir
termux-wake-lock

# 2. Mata processos antigos (limpeza)
pkill -f proxy_agent.py
pkill -f skuld-core

# 3. Inicia o Core e o Agente em background
nohup ~/skuld/bin/skuld-core > ~/skuld/logs/core.log 2>&1 &
sleep 2
nohup python ~/skuld/agents/sys/proxy_agent.py > ~/skuld/logs/proxy.log 2>&1 &

echo "✅ Sistema rodando em background!"
echo "📡 Use 'tail -f ~/skuld/logs/proxy.log' para monitorar."
