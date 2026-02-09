package internal

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"skuld/core/internal/database"
)

// Versão global para consistência no sistema
const CoreVersion = "v1.0.0-rc1"

type Message struct {
	ID     string          `json:"id"`
	Cmd    string          `json:"cmd"`
	Agent  string          `json:"agent"`
	Params json.RawMessage `json:"params"`
}

type Response struct {
	ID      string      `json:"id"`
	Status  string      `json:"status"`
	Result  interface{} `json:"result,omitempty"`
	Error   string      `json:"error,omitempty"`
	Latency int64       `json:"latency_ms"`
}

var (
	startTime int64
	handlers  = make(map[string]func(Message) (interface{}, error))
	agents    = make(map[string]time.Time)
	mu        sync.RWMutex
)

func registerHandlers() {
	mu.Lock()
	defer mu.Unlock()

	// Handshake de Agentes
	handlers["register_agent"] = func(m Message) (interface{}, error) {
		mu.Lock()
		agents[m.Agent] = time.Now()
		mu.Unlock()
		log.Printf("[CORE] Agente registrado: %s", m.Agent)
		return map[string]string{"message": "Conectado ao Skuld Core", "version": CoreVersion}, nil
	}

	handlers["ping"] = func(m Message) (interface{}, error) {
		return map[string]interface{}{"pong": time.Now().Format(time.RFC3339)}, nil
	}

	handlers["status"] = func(m Message) (interface{}, error) {
		mu.RLock()
		activeAgents := len(agents)
		mu.RUnlock()
		return map[string]interface{}{
			"version":       CoreVersion,
			"uptime":        fmt.Sprintf("%ds", time.Now().Unix()-startTime),
			"active_agents": activeAgents,
			"state":         "operational",
		}, nil
	}

	handlers["notify_user"] = func(m Message) (interface{}, error) {
		var p struct{ Title, Msg string }
		json.Unmarshal(m.Params, &p)
		exec.Command("termux-notification", "--title", p.Title, "--content", p.Msg).Run()
		return "ok", nil
	}

	// Comando Help Dinâmico
	handlers["help"] = func(m Message) (interface{}, error) {
		mu.RLock()
		cmds := make([]string, 0, len(handlers))
		for k := range handlers {
			cmds = append(cmds, k)
		}
		mu.RUnlock()
		return map[string]interface{}{
			"available_commands": cmds,
			"system": "Skuld MCP",
		}, nil
	}
}

func handleConnection(conn net.Conn) {
	defer conn.Close()
	dec, enc := json.NewDecoder(conn), json.NewEncoder(conn)

	for {
		var msg Message
		if err := dec.Decode(&msg); err != nil {
			return
		}
		start := time.Now()

		database.SaveIntention(msg.ID, msg.Cmd, msg.Agent, string(msg.Params), 50)

		mu.RLock()
		h, exists := handlers[msg.Cmd]
		mu.RUnlock()

		var resp Response
		resp.ID = msg.ID

		if !exists {
			resp.Status = "error"
			resp.Error = "comando desconhecido: " + msg.Cmd
			log.Printf("[WARN] Comando não encontrado: %s", msg.Cmd)
		} else {
			res, err := h(msg)
			if err != nil {
				resp.Status = "error"
				resp.Error = err.Error()
			} else {
				resp.Status = "ok"
				resp.Result = res
			}
		}

		resp.Latency = time.Since(start).Milliseconds()
		database.UpdateIntention(msg.ID, resp.Status, "", "", resp.Error)
		enc.Encode(resp)
	}
}

func RunWithSignalHandling(socketPath, dataDir string) error {
	startTime = time.Now().Unix()
	database.Init(dataDir)
	registerHandlers()

	os.Remove(socketPath)
	l, err := net.Listen("unix", socketPath)
	if err != nil {
		return err
	}
	os.Chmod(socketPath, 0777)

	log.Printf("[INFO] Servidor UDS pronto em %s", socketPath)

	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
		<-sig
		l.Close()
		os.Remove(socketPath)
		log.Println("[INFO] Encerrando Core Skuld.")
		os.Exit(0)
	}()

	for {
		conn, err := l.Accept()
		if err == nil {
			go handleConnection(conn)
		}
	}
}
