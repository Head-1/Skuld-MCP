"""
Configurações para os agentes do Skuld.
"""

DEFAULT_CONFIG = {
    # Socket do Core
    "socket_path": "/data/data/com.termux/files/usr/tmp/skuld.sock",
    
    # Battery Agent
    "battery": {
        "poll_interval": 30,      # segundos
        "low_threshold": 20,      # porcentagem
        "critical_threshold": 15, # porcentagem
        "debug": False
    },
    
    # Notifier Agent
    "notifier": {
        "poll_interval": 10,      # segundos
        "db_path": "/data/data/com.termux/files/home/.skuld/skuld.db"
    }
}
