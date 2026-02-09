// Package database gerencia a conexão SQLite com WAL e schema do Skuld
package database

import (
    "database/sql"
    "fmt"
    "log"
    "os"
    "path/filepath"
    "time"

    _ "modernc.org/sqlite" // Driver Pure Go SQLite (SEM CGO!)
)

var db *sql.DB

// Init inicializa o banco de dados com WAL e cria o schema
func Init(dataDir string) error {
    dbPath := filepath.Join(dataDir, "skuld.db")
    
    // Criar diretório se não existir
    if err := os.MkdirAll(dataDir, 0755); err != nil {
        return fmt.Errorf("falha ao criar diretório de dados: %w", err)
    }

    // Abrir conexão
    var err error
    db, err = sql.Open("sqlite", dbPath)
    if err != nil {
        return fmt.Errorf("falha ao abrir banco de dados: %w", err)
    }

    // Configurar conexão
    db.SetMaxOpenConns(1) // SQLite trabalha melhor com 1 conexão
    db.SetMaxIdleConns(1)
    db.SetConnMaxLifetime(10 * time.Minute)

    // Configurar WAL para resiliência em Android
    if _, err := db.Exec(`
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        PRAGMA foreign_keys = ON;
        PRAGMA busy_timeout = 5000;
    `); err != nil {
        return fmt.Errorf("falha ao configurar WAL: %w", err)
    }

    // Criar schema
    if err := createSchema(); err != nil {
        return fmt.Errorf("falha ao criar schema: %w", err)
    }

    log.Printf("Banco de dados inicializado em: %s", dbPath)
    return nil
}

// GetDB retorna a conexão do banco de dados
func GetDB() *sql.DB {
    return db
}

// Close fecha a conexão com o banco de dados
func Close() error {
    if db != nil {
        return db.Close()
    }
    return nil
}

func createSchema() error {
    schema := `
    -- Tabela principal: Intenções do Usuário
    CREATE TABLE IF NOT EXISTS intentions (
        id TEXT PRIMARY KEY,
        timestamp INTEGER NOT NULL,
        cmd TEXT NOT NULL,
        agent TEXT NOT NULL,
        params TEXT,
        priority INTEGER DEFAULT 50,
        
        -- Estado da execução
        status TEXT DEFAULT 'pending',
        attempt_count INTEGER DEFAULT 0,
        last_attempt INTEGER,
        
        -- Para retomada de estado
        checkpoint TEXT,
        result TEXT,
        error TEXT
    );

    -- Índices otimizados para Android
    CREATE INDEX IF NOT EXISTS idx_intentions_status ON intentions(status, priority);
    CREATE INDEX IF NOT EXISTS idx_intentions_agent ON intentions(agent, status);
    CREATE INDEX IF NOT EXISTS idx_intentions_timestamp ON intentions(timestamp DESC);

    -- Tabela de Recursos do Sistema
    CREATE TABLE IF NOT EXISTS system_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp INTEGER NOT NULL,
        metric TEXT NOT NULL,
        value REAL NOT NULL,
        tags TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_telemetry_recent ON system_telemetry(metric, timestamp DESC);

    -- Tabela de Autenticação
    CREATE TABLE IF NOT EXISTS auth_keys (
        agent_id TEXT PRIMARY KEY,
        public_key TEXT NOT NULL,
        permissions TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        last_used INTEGER,
        is_active INTEGER DEFAULT 1
    );

    -- Tabela de Configuração
    CREATE TABLE IF NOT EXISTS user_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at INTEGER NOT NULL
    );
    `

    if _, err := db.Exec(schema); err != nil {
        return fmt.Errorf("erro ao criar schema: %w", err)
    }

    // Inserir configurações padrão
    defaultConfigs := []struct {
        key   string
        value string
    }{
        {"battery_threshold", "15"},
        {"auto_pause_on_low_battery", "true"},
        {"max_retry_attempts", "3"},
        {"log_retention_days", "7"},
        {"uds_socket_path", "/data/data/com.termux/files/usr/tmp/skuld.sock"},
    }

    for _, cfg := range defaultConfigs {
        _, err := db.Exec(`
            INSERT OR IGNORE INTO user_config (key, value, updated_at) 
            VALUES (?, ?, ?)
        `, cfg.key, cfg.value, time.Now().Unix())
        if err != nil {
            log.Printf("Aviso: não pôde inserir config padrão %s: %v", cfg.key, err)
        }
    }

    log.Println("Schema do banco de dados criado com sucesso")
    return nil
}

// SaveIntention salva uma nova intenção no diário
func SaveIntention(id, cmd, agent, params string, priority int) error {
    _, err := db.Exec(`
        INSERT INTO intentions (id, timestamp, cmd, agent, params, priority, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    `, id, time.Now().Unix(), cmd, agent, params, priority)
    return err
}

// UpdateIntention atualiza o estado de uma intenção
func UpdateIntention(id, status, checkpoint, result, errorMsg string) error {
    query := `
        UPDATE intentions 
        SET status = ?,
            last_attempt = ?,
            attempt_count = attempt_count + 1,
            checkpoint = COALESCE(?, checkpoint),
            result = COALESCE(?, result),
            error = COALESCE(?, error)
        WHERE id = ?
    `
    _, err := db.Exec(query, status, time.Now().Unix(), checkpoint, result, errorMsg, id)
    return err
}

// GetPendingIntentions retorna intenções pendentes
func GetPendingIntentions(limit int) ([]map[string]interface{}, error) {
    rows, err := db.Query(`
        SELECT id, cmd, agent, params, priority, checkpoint
        FROM intentions 
        WHERE status = 'pending' 
        ORDER BY priority ASC, timestamp ASC
        LIMIT ?
    `, limit)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var intentions []map[string]interface{}
    for rows.Next() {
        var id, cmd, agent, params string
        var priority int
        var checkpoint sql.NullString
        if err := rows.Scan(&id, &cmd, &agent, &params, &priority, &checkpoint); err != nil {
            return nil, err
        }
        intentions = append(intentions, map[string]interface{}{
            "id":         id,
            "cmd":        cmd,
            "agent":      agent,
            "params":     params,
            "priority":   priority,
            "checkpoint": checkpoint.String,
        })
    }
    return intentions, nil
}
