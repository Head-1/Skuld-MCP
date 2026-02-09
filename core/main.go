package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"skuld/core/internal"
)

type Config struct {
	SocketPath string `json:"socket_path"`
	DataDir    string `json:"data_dir"`
	LogFile    string `json:"log_file"`
}

func main() {
	configPath := flag.String("config", "../config.json", "Caminho para o arquivo de configuração")
	flag.Parse()

	// 1. Carregar Configuração
	file, err := os.Open(*configPath)
	if err != nil {
		fmt.Printf("Erro ao carregar config: %v\n", err)
		// Fallback para flags manuais se o arquivo não existir (para compatibilidade)
		fmt.Println("Tentando flags manuais...")
	} else {
		defer file.Close()
		var cfg Config
		if err := json.NewDecoder(file).Decode(&cfg); err == nil {
			// 2. Configurar Logger para Arquivo vindo do JSON
			logDir := filepath.Dir(cfg.LogFile)
			os.MkdirAll(logDir, 0755)
			logOut, err := os.OpenFile(cfg.LogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
			if err == nil {
				log.SetOutput(logOut)
			}
			log.Printf(">>> SKULD CORE INICIANDO (%s) <<<", cfg.SocketPath)
			if err := internal.RunWithSignalHandling(cfg.SocketPath, cfg.DataDir); err != nil {
				log.Fatalf("Erro fatal: %v", err)
			}
			return
		}
	}
    fmt.Println("Falha ao carregar config.json. Use -config corretamente.")
}
