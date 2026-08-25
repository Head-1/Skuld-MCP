#!/bin/bash

# Definições Absolutas
BASE_DIR="/data/data/com.termux/files/home/skuld"
SOCKET_FILE="/data/data/com.termux/files/usr/tmp/skuld.sock"
BIN_CORE="$BASE_DIR/bin/skuld-core"
BRIDGE_SCRIPT="$BASE_DIR/agents/sys/bridge_agent.py"

cd "$BASE_DIR" || exit 1

case "$1" in
    start)
        # 1. Iniciar Core
        if pgrep -f "skuld-core" > /dev/null; then
            echo "[!] Core já rodando."
        else
            echo "[+] Iniciando Core..."
            # Remove socket antigo se existir para evitar erro de "address already in use"
            rm -f "$SOCKET_FILE"
            # Inicia com nohup para desatrelar do terminal atual
            nohup "$BIN_CORE" -config="$BASE_DIR/config.json" > "$BASE_DIR/logs/core.log" 2>&1 &
        fi

        # 2. Iniciar Bridge
        if pgrep -f "bridge_agent.py" > /dev/null; then
            echo "[!] Bridge já rodando."
        else
            echo "[+] Iniciando Bridge..."
            nohup python "$BRIDGE_SCRIPT" > "$BASE_DIR/logs/bridge.log" 2>&1 &
        fi
        ;;
    stop)
        echo "[!] Parando serviços..."
        pkill -f "skuld-core"
        pkill -f "bridge_agent.py"
        rm -f "$SOCKET_FILE"
        echo "[ok] Skuld offline."
        ;;
    status)
        if [ -S "$SOCKET_FILE" ]; then
            echo "Core: ONLINE (Socket ativo)"
        else
            echo "Core: OFFLINE"
        fi
        ;;
    *)
        echo "Uso: $0 {start|stop|status}"
        exit 1
        ;;
esac
