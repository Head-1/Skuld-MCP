#!/bin/bash

# Cores para o output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}💀 Iniciando Instalador do Skuld MCP...${NC}"

# 1. Dependências
echo -e "[-] Verificando dependências..."
pkg install golang python termux-api sqlite -y

# 2. Pastas
echo -e "[-] Criando estrutura de diretórios..."
mkdir -p logs data core/internal/database agents/common agents/sys bin

# 3. Configuração Inicial
if [ ! -f config.json ]; then
    echo -e "[-] Gerando config.json padrão..."
    cat <<EOF > config.json
{
    "socket_path": "$HOME/../usr/tmp/skuld.sock",
    "data_dir": "$HOME/skuld/data",
    "log_file": "$HOME/skuld/logs/core.log",
    "version": "v1.0.0-rc1"
}
EOF
fi

# 4. Compilação do Core
echo -e "[-] Compilando Skuld Core..."
cd core
CGO_ENABLED=0 go build -o skuld-core main.go
mv skuld-core ../bin/
cd ..

# 5. Permissões
chmod +x bin/skuld-core
chmod +x skuld-cli.py

echo -e "${GREEN}[+] Instalação concluída com sucesso!${NC}"
echo -e "Para iniciar o Skuld, use: ${BLUE}./bin/skuld-core -config=config.json &${NC}"
