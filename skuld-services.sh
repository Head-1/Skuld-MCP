#!/bin/bash

case "$1" in
    start)
        echo "Starting Skuld Core..."
        ./bin/skuld-core -config=config.json > /dev/null 2>&1 &
        sleep 2
        echo "Starting Bridge Agent..."
        python agents/sys/bridge_agent.py > logs/bridge.log 2>&1 &
        echo "Skuld is UP."
        ;;
    stop)
        echo "Stopping Skuld..."
        pkill -f skuld-core
        pkill -f bridge_agent.py
        echo "Skuld is DOWN."
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        ;;
esac
