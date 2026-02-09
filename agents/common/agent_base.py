#!/usr/bin/env python3
"""
Skuld Agent Base Class - Refatorado
Classe base para todos os agentes do Skuld MCP.
Fornece comunicação padronizada com o Core via Unix Domain Sockets.
"""

import socket
import json
import os
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, asdict
from enum import Enum


class MessagePriority(Enum):
    """Prioridades padronizadas para mensagens do Skuld."""
    CRITICAL = 1     # Emergência máxima (ex: bateria 5%)
    HIGH = 10        # Alta prioridade (ex: bateria 15%)
    MEDIUM = 20      # Prioridade média (ex: notificações importantes)
    NORMAL = 50      # Prioridade normal (telemetria, logs)
    LOW = 100        # Baixa prioridade (tarefas em background)


class AgentStatus(Enum):
    """Status possíveis para um agente."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class SkuldMessage:
    """Estrutura de mensagem padronizada para comunicação com o Core."""
    cmd: str
    agent: str
    priority: int = MessagePriority.NORMAL.value
    params: Dict[str, Any] = None
    id: str = None
    
    def __post_init__(self):
        """Inicializações pós-criação."""
        if self.id is None:
            self.id = f"{self.agent}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        if self.params is None:
            self.params = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte a mensagem para dicionário."""
        return {
            "id": self.id,
            "cmd": self.cmd,
            "agent": self.agent,
            "priority": self.priority,
            "params": self.params,
            "timestamp": datetime.now().isoformat()
        }
    
    def to_json(self) -> str:
        """Converte a mensagem para JSON."""
        return json.dumps(self.to_dict())


@dataclass
class SkuldResponse:
    """Estrutura de resposta padronizada do Core."""
    id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkuldResponse':
        """Cria uma resposta a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            status=data.get("status", "error"),
            result=data.get("result"),
            error=data.get("error"),
            latency_ms=data.get("latency_ms")
        )
    
    def is_ok(self) -> bool:
        """Verifica se a resposta foi bem-sucedida."""
        return self.status == "ok"
    
    def is_error(self) -> bool:
        """Verifica se a resposta contém erro."""
        return self.status == "error" or self.error is not None


class SkuldAgent:
    """
    Classe base para todos os agentes do Skuld.
    
    Atributos:
        agent_id: Identificador único do agente
        socket_path: Caminho do socket UDS do Core
        debug: Se True, ativa logs detalhados
        status: Status atual do agente
        reconnect_attempts: Número de tentativas de reconexão
    """
    
    def __init__(
        self,
        agent_id: str,
        socket_path: str = "/data/data/com.termux/files/usr/tmp/skuld.sock",
        debug: bool = False
    ):
        """
        Inicializa o agente.
        
        Args:
            agent_id: Nome/ID único do agente
            socket_path: Caminho para o socket UDS do Core
            debug: Ativar modo debug com logs detalhados
        """
        self.agent_id = agent_id
        self.socket_path = socket_path
        self.debug = debug
        self.status = AgentStatus.INITIALIZING
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.socket_timeout = 10  # segundos
        
        # Configurar logging
        self._setup_logging()
        
        # Log de inicialização
        self.log(f"Agente '{agent_id}' inicializando...")
        self.log(f"Socket: {socket_path}")
        self.log(f"Debug: {debug}")
    
    def _setup_logging(self):
        """Configura o sistema de logging do agente."""
        # Em produção, isso pode ser expandido para arquivos de log
        pass
    
    def log(self, message: str, level: str = "INFO"):
        """
        Log de mensagens com formatação consistente.
        
        Args:
            message: Mensagem a ser logada
            level: Nível do log (INFO, WARN, ERROR, DEBUG)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Se não for debug, ignora logs DEBUG
        if level == "DEBUG" and not self.debug:
            return
        
        # Cores para terminal (opcional)
        colors = {
            "INFO": "\033[94m",   # Azul
            "WARN": "\033[93m",   # Amarelo
            "ERROR": "\033[91m",  # Vermelho
            "DEBUG": "\033[90m",  # Cinza
            "RESET": "\033[0m"    # Reset
        }
        
        # Formatar mensagem
        log_message = f"[{timestamp}] [{self.agent_id}] [{level}] {message}"
        
        # Adicionar cor se suportado
        if os.isatty(1) and level in colors:
            print(f"{colors[level]}{log_message}{colors['RESET']}")
        else:
            print(log_message)
    
    def _check_socket(self) -> bool:
        """
        Verifica se o socket do Core está disponível.
        
        Returns:
            True se o socket existe e é acessível, False caso contrário
        """
        if not os.path.exists(self.socket_path):
            self.log(f"Socket não encontrado: {self.socket_path}", "ERROR")
            return False
        
        # Verificar se é realmente um socket
        if not os.access(self.socket_path, os.W_OK):
            self.log(f"Sem permissão de escrita no socket: {self.socket_path}", "WARN")
        
        return True
    
    def _create_socket(self) -> Optional[socket.socket]:
        """
        Cria e configura um socket para comunicação.
        
        Returns:
            Socket configurado ou None em caso de erro
        """
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.socket_timeout)
            return sock
        except socket.error as e:
            self.log(f"Erro ao criar socket: {e}", "ERROR")
            return None
    
    def send_message(self, message: Union[SkuldMessage, Dict[str, Any]]) -> Optional[SkuldResponse]:
        """
        Envia uma mensagem para o Core e retorna a resposta.
        
        Args:
            message: SkuldMessage ou dicionário com a mensagem
            
        Returns:
            SkuldResponse com a resposta ou None em caso de erro crítico
        """
        # Converter para SkuldMessage se necessário
        if isinstance(message, dict):
            message = SkuldMessage(**message)
        
        # Verificar se o Core está disponível
        if not self._check_socket():
            return SkuldResponse(
                id=message.id,
                status="error",
                error=f"Core não disponível em {self.socket_path}"
            )
        
        # Criar socket
        sock = self._create_socket()
        if sock is None:
            return SkuldResponse(
                id=message.id,
                status="error",
                error="Falha ao criar socket"
            )
        
        try:
            # Conectar ao Core
            start_time = time.time()
            sock.connect(self.socket_path)
            connect_time = (time.time() - start_time) * 1000
            
            if self.debug:
                self.log(f"Conexão estabelecida em {connect_time:.1f}ms", "DEBUG")
            
            # Preparar payload (JSON-L: JSON + newline)
            payload = message.to_json() + "\n"
            
            # Enviar mensagem
            sock.sendall(payload.encode('utf-8'))
            
            # Receber resposta
            response_data = sock.recv(8192).decode('utf-8').strip()
            
            # Parse da resposta
            try:
                response_dict = json.loads(response_data)
                response = SkuldResponse.from_dict(response_dict)
                
                # Calcular latência total
                total_time = (time.time() - start_time) * 1000
                response.latency_ms = int(total_time)
                
                if self.debug:
                    self.log(f"Resposta recebida em {total_time:.1f}ms: {response.status}", "DEBUG")
                
                # Resetar contador de reconexões
                self.reconnect_attempts = 0
                
                return response
                
            except json.JSONDecodeError as e:
                self.log(f"Resposta JSON inválida: {response_data}", "ERROR")
                return SkuldResponse(
                    id=message.id,
                    status="error",
                    error=f"Resposta JSON inválida: {str(e)}"
                )
                
        except socket.timeout:
            self.log(f"Timeout ao comunicar com o Core ({self.socket_timeout}s)", "ERROR")
            return SkuldResponse(
                id=message.id,
                status="error",
                error=f"Timeout de {self.socket_timeout}s"
            )
            
        except ConnectionRefusedError:
            self.log(f"Conexão recusada pelo Core", "ERROR")
            return SkuldResponse(
                id=message.id,
                status="error",
                error="Conexão recusada (Core pode não estar rodando)"
            )
            
        except socket.error as e:
            self.log(f"Erro de socket: {e}", "ERROR")
            self.reconnect_attempts += 1
            
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                self.log(f"Máximo de tentativas de reconexão atingido ({self.max_reconnect_attempts})", "ERROR")
                self.status = AgentStatus.ERROR
            
            return SkuldResponse(
                id=message.id,
                status="error",
                error=f"Erro de socket: {str(e)}"
            )
            
        except Exception as e:
            self.log(f"Erro inesperado: {e}", "ERROR")
            return SkuldResponse(
                id=message.id,
                status="error",
                error=f"Erro inesperado: {str(e)}"
            )
            
        finally:
            # Fechar socket
            try:
                sock.close()
            except:
                pass
    
    def send_command(
        self,
        cmd: str,
        params: Dict[str, Any] = None,
        priority: int = MessagePriority.NORMAL.value
    ) -> Optional[SkuldResponse]:
        """
        Método de conveniência para enviar comandos simples.
        
        Args:
            cmd: Comando a ser executado
            params: Parâmetros do comando
            priority: Prioridade da mensagem
            
        Returns:
            SkuldResponse com a resposta
        """
        message = SkuldMessage(
            cmd=cmd,
            agent=self.agent_id,
            priority=priority,
            params=params or {}
        )
        
        return self.send_message(message)
    
    def report_telemetry(
        self,
        metric: str,
        value: Union[int, float, str, bool],
        tags: Dict[str, str] = None,
        additional_data: Dict[str, Any] = None
    ) -> Optional[SkuldResponse]:
        """
        Reporta dados de telemetria para o Core.
        
        Args:
            metric: Nome da métrica
            value: Valor da métrica
            tags: Tags para categorização
            additional_data: Dados adicionais
            
        Returns:
            SkuldResponse com a resposta
        """
        params = {
            "metric": metric,
            "value": value,
            "tags": tags or {},
            "timestamp": datetime.now().isoformat()
        }
        
        if additional_data:
            params["data"] = additional_data
        
        return self.send_command("telemetry_push", params, MessagePriority.NORMAL.value)
    
    def ping(self) -> bool:
        """
        Testa a conexão com o Core enviando um ping.
        
        Returns:
            True se o Core respondeu, False caso contrário
        """
        self.log("Testando conexão com o Core...", "DEBUG")
        
        response = self.send_command("ping", {"agent": self.agent_id})
        
        if response and response.is_ok():
            self.log(f"Conexão com Core OK (latência: {response.latency_ms}ms)", "INFO")
            return True
        else:
            error_msg = response.error if response else "Sem resposta"
            self.log(f"Conexão com Core falhou: {error_msg}", "ERROR")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Obtém o status do Core.
        
        Returns:
            Dicionário com informações de status
        """
        response = self.send_command("status")
        
        if response and response.is_ok():
            return response.result or {}
        else:
            return {"error": "Falha ao obter status", "agent_status": self.status.value}
    
    def test_core_connection(self, max_attempts: int = 3) -> bool:
        """
        Testa a conexão com o Core com múltiplas tentativas.
        
        Args:
            max_attempts: Número máximo de tentativas
            
        Returns:
            True se a conexão foi estabelecida, False caso contrário
        """
        self.log(f"Testando conexão com Core (max {max_attempts} tentativas)...")
        
        for attempt in range(1, max_attempts + 1):
            self.log(f"Tentativa {attempt}/{max_attempts}...", "DEBUG")
            
            if self.ping():
                return True
            
            if attempt < max_attempts:
                self.log(f"Aguardando 2 segundos antes da próxima tentativa...", "DEBUG")
                time.sleep(2)
        
        self.log(f"Falha após {max_attempts} tentativas", "ERROR")
        return False
    
    def start(self):
        """Inicia o agente (método abstrato a ser implementado)."""
        raise NotImplementedError("Método start() deve ser implementado pela subclasse")
    
    def stop(self):
        """Para o agente graciosamente."""
        self.status = AgentStatus.STOPPING
        self.log("Parando agente...")
        # Subclasses devem implementar limpeza específica
        self.status = AgentStatus.STOPPED
    
    def run(self):
        """Executa o agente (método abstrato a ser implementado)."""
        raise NotImplementedError("Método run() deve ser implementado pela subclasse")


# ========== EXEMPLOS DE USO ==========

def example_usage():
    """Exemplos de uso da classe base."""
    
    # Exemplo 1: Agente simples
    print("=" * 50)
    print("Exemplo 1: Agente Simples")
    print("=" * 50)
    
    class TestAgent(SkuldAgent):
        def run(self):
            self.log("Agente de teste iniciado")
            
            # Testar conexão
            if not self.test_core_connection():
                self.log("Não foi possível conectar ao Core")
                return
            
            # Enviar ping
            response = self.send_command("ping")
            print(f"Resposta do ping: {response}")
            
            # Enviar telemetria
            telemetry_response = self.report_telemetry(
                metric="test_metric",
                value=42.5,
                tags={"test": "true", "agent": "test"}
            )
            print(f"Resposta da telemetria: {telemetry_response}")
            
            # Obter status
            status = self.get_status()
            print(f"Status do Core: {status}")
    
    # Criar e executar agente de teste
    agent = TestAgent("example_agent", debug=True)
    agent.run()
    
    print("\n" + "=" * 50)
    print("Exemplo 2: Uso Direto")
    print("=" * 50)
    
    # Exemplo 2: Uso direto da classe base
    base_agent = SkuldAgent("direct_agent", debug=True)
    
    # Criar mensagem personalizada
    custom_message = SkuldMessage(
        cmd="config_get",
        agent="direct_agent",
        priority=MessagePriority.NORMAL.value,
        params={"key": "battery_threshold"}
    )
    
    # Enviar mensagem
    response = base_agent.send_message(custom_message)
    print(f"Resposta da config_get: {response}")
    
    print("\n" + "=" * 50)
    print("Exemplo 3: Métodos de Conveniência")
    print("=" * 50)
    
    # Métodos de conveniência
    print("Métodos disponíveis:")
    print("- send_command(cmd, params, priority)")
    print("- report_telemetry(metric, value, tags, data)")
    print("- ping()")
    print("- get_status()")
    print("- test_core_connection(max_attempts)")
    
    print("\n" + "=" * 50)
    print("✅ Exemplos concluídos")
    print("=" * 50)


if __name__ == "__main__":
    # Executar exemplos se o script for rodado diretamente
    example_usage()
