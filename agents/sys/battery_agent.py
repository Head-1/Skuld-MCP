#!/usr/bin/env python3
"""
Skuld Battery Agent - Versão 3.0
Monitora a bateria do Android e reporta mudanças para o Core Skuld.
Integrado com a nova agent_base.py refatorada.
"""

import sys
import os
import subprocess
import json
import time
import signal
from datetime import datetime
from typing import Dict, Any, Optional

# Adiciona o caminho base para importar o SkuldAgent
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'common'))
from agent_base import SkuldAgent, SkuldMessage, MessagePriority, AgentStatus


class BatteryAgent(SkuldAgent):
    """Agente especializado em monitoramento de bateria para Android via Termux."""
    
    def __init__(
        self,
        socket_path: str = "/data/data/com.termux/files/usr/tmp/skuld.sock",
        debug: bool = False
    ):
        """
        Inicializa o agente de bateria.
        
        Args:
            socket_path: Caminho para o socket UDS do Core
            debug: Ativar modo debug com logs detalhados
        """
        super().__init__(
            agent_id="sys_battery",
            socket_path=socket_path,
            debug=debug
        )
        
        # Estado anterior para detecção de mudanças
        self.last_percentage: Optional[int] = None
        self.last_status: Optional[str] = None
        self.last_health: Optional[str] = None
        self.last_temperature: Optional[float] = None
        
        # Configurações personalizáveis
        self.poll_interval: int = 30  # segundos (otimizado para economia de bateria)
        self.low_battery_threshold: int = 20  # porcentagem
        self.critical_battery_threshold: int = 15  # porcentagem
        
        # Controle de execução
        self.running: bool = True
        self.consecutive_errors: int = 0
        self.max_consecutive_errors: int = 3
        
        # Configurar tratamento de sinais
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Log de inicialização
        self.log(f"Inicializado com limiar baixo: {self.low_battery_threshold}%", "INFO")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """
        Lida com sinais de desligamento gracioso.
        
        Args:
            signum: Número do sinal recebido
            frame: Frame de execução atual
        """
        self.log(f"Recebido sinal {signum}, desligando graciosamente...", "INFO")
        self.running = False
        self.status = AgentStatus.STOPPING
    
    def get_battery_info(self) -> Optional[Dict[str, Any]]:
        """
        Obtém informações da bateria usando termux-battery-status.
        
        Returns:
            Dicionário com informações da bateria ou None em caso de erro.
        """
        try:
            self.log("Obtendo status da bateria...", "DEBUG")
            
            # Executa o comando termux-battery-status com timeout
            result = subprocess.run(
                ["termux-battery-status"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True
            )
            
            # Parse do JSON
            battery_data = json.loads(result.stdout)
            
            # Validação básica dos dados
            if "percentage" not in battery_data or "status" not in battery_data:
                self.log("Dados de bateria incompletos", "WARN")
                return None
            
            self.log(f"Dados obtidos: {battery_data.get('percentage', 0)}%", "DEBUG")
            return battery_data
            
        except subprocess.TimeoutExpired:
            self.log("Timeout ao executar termux-battery-status", "ERROR")
            return None
            
        except subprocess.CalledProcessError as e:
            self.log(f"termux-battery-status falhou com código {e.returncode}", "ERROR")
            if e.stderr:
                self.log(f"Stderr: {e.stderr}", "DEBUG")
            return None
            
        except json.JSONDecodeError as e:
            self.log(f"Falha ao decodificar JSON: {e}", "ERROR")
            return None
            
        except FileNotFoundError:
            self.log("termux-battery-status não encontrado", "ERROR")
            self.log("Instale com: pkg install termux-api", "INFO")
            self.log("Conceda permissões ao Termux nas configurações do Android", "INFO")
            return None
            
        except Exception as e:
            self.log(f"Erro inesperado ao obter status da bateria: {e}", "ERROR")
            return None
    
    def has_battery_changed(self, current_info: Dict[str, Any]) -> bool:
        """
        Verifica se houve mudança significativa no status da bateria.
        
        Args:
            current_info: Informações atuais da bateria
            
        Returns:
            True se houve mudança significativa, False caso contrário
        """
        current_percentage = current_info.get("percentage")
        current_status = current_info.get("status")
        current_health = current_info.get("health", "unknown")
        current_temp = current_info.get("temperature", 0)
        
        # Primeira leitura - sempre reportar
        if self.last_percentage is None:
            self.log("Primeira leitura da bateria", "DEBUG")
            return True
        
        # Verificar mudanças significativas
        percentage_changed = current_percentage != self.last_percentage
        status_changed = current_status != self.last_status
        health_changed = current_health != self.last_health
        
        # Temperatura: apenas mudanças significativas (> 0.5°C)
        temp_changed = abs(current_temp - self.last_temperature) >= 0.5
        
        # Determinar se deve reportar
        should_report = any([
            percentage_changed,
            status_changed,
            health_changed,
            temp_changed
        ])
        
        if self.debug and should_report:
            changes = []
            if percentage_changed:
                changes.append(f"porcentagem: {self.last_percentage}% → {current_percentage}%")
            if status_changed:
                changes.append(f"status: {self.last_status} → {current_status}")
            if health_changed:
                changes.append(f"saúde: {self.last_health} → {current_health}")
            if temp_changed:
                changes.append(f"temperatura: {self.last_temperature} → {current_temp}")
            
            self.log(f"Mudanças detectadas: {', '.join(changes)}", "DEBUG")
        
        return should_report
    
    def determine_priority(self, percentage: int, status: str) -> int:
        """
        Determina a prioridade da mensagem baseada no status da bateria.
        
        Args:
            percentage: Porcentagem atual da bateria
            status: Status atual (charging/discharging)
            
        Returns:
            Valor de prioridade (menor = maior prioridade)
        """
        status_upper = status.upper() if status else "UNKNOWN"
        
        if percentage <= self.critical_battery_threshold:
            self.log(f"Bateria CRÍTICA: {percentage}%", "WARN")
            return MessagePriority.CRITICAL.value
        
        elif percentage <= self.low_battery_threshold:
            self.log(f"Bateria BAIXA: {percentage}%", "WARN")
            return MessagePriority.HIGH.value
        
        elif status_upper == "DISCHARGING" and percentage <= 30:
            return MessagePriority.MEDIUM.value
        
        else:
            return MessagePriority.NORMAL.value
    
    def send_battery_update(self, battery_info: Dict[str, Any]) -> bool:
        """
        Envia atualização da bateria para o Core.
        
        Args:
            battery_info: Informações completas da bateria
            
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            percentage = battery_info.get("percentage", 0)
            status = battery_info.get("status", "UNKNOWN")
            health = battery_info.get("health", "UNKNOWN")
            status_upper = status.upper()
            
            # Determinar prioridade
            priority = self.determine_priority(percentage, status)
            
            # Preparar dados estruturados para envio
            battery_data = {
                "percentage": percentage,
                "status": status,
                "health": health,
                "temperature": battery_info.get("temperature", 0),
                "voltage": battery_info.get("voltage", 0),
                "current": battery_info.get("current", 0),
                "capacity": battery_info.get("capacity", 0),
                "charging": status_upper == "CHARGING",
                "timestamp": datetime.now().isoformat(),
                "plugged": status_upper in ["CHARGING", "FULL"]
            }
            
            # Criar mensagem usando a nova classe SkuldMessage
            message = SkuldMessage(
                cmd="battery_update",
                agent=self.agent_id,
                priority=priority,
                params=battery_data
            )
            
            # Enviar para o Core
            response = self.send_message(message)
            
            if response and response.is_ok():
                result = response.result or {}
                
                # Log apropriado baseado no resultado
                if result.get("automation"):
                    self.log(
                        f"Bateria {percentage}%: Automação ativada "
                        f"(<{self.low_battery_threshold}%)",
                        "WARN"
                    )
                else:
                    self.log(
                        f"Bateria reportada: {percentage}% ({status}) - "
                        f"Prioridade: {priority}",
                        "INFO"
                    )
                
                # Resetar contador de erros em caso de sucesso
                self.consecutive_errors = 0
                return True
                
            else:
                error_msg = response.error if response else "Resposta inválida"
                self.log(f"Erro ao reportar bateria: {error_msg}", "ERROR")
                self.consecutive_errors += 1
                return False
                
        except Exception as e:
            self.log(f"Erro ao enviar atualização: {e}", "ERROR")
            self.consecutive_errors += 1
            return False
    
    def update_local_state(self, battery_info: Dict[str, Any]) -> None:
        """
        Atualiza o estado local para comparações futuras.
        
        Args:
            battery_info: Informações atuais da bateria
        """
        self.last_percentage = battery_info.get("percentage")
        self.last_status = battery_info.get("status")
        self.last_health = battery_info.get("health", "unknown")
        self.last_temperature = battery_info.get("temperature", 0)
        
        if self.debug:
            self.log(
                f"Estado atualizado: {self.last_percentage}%, "
                f"{self.last_status}, {self.last_health}",
                "DEBUG"
            )
    
    def test_connections(self) -> bool:
        """
        Testa todas as conexões necessárias antes de iniciar.
        
        Returns:
            True se todos os testes passarem, False caso contrário
        """
        self.log("Iniciando testes de conexão...", "INFO")
        
        # 1. Testar conexão com o Core
        self.log("Testando conexão com o Core...", "DEBUG")
        if not self.test_core_connection(max_attempts=2):
            self.log("FALHA: Não foi possível conectar ao Core Skuld", "ERROR")
            self.log("Verifique se o Core está rodando:", "INFO")
            self.log("  cd ~/skuld/core && go run main.go", "INFO")
            return False
        
        # 2. Testar acesso à API da bateria
        self.log("Testando acesso à API da bateria...", "DEBUG")
        battery_info = self.get_battery_info()
        if not battery_info:
            self.log("FALHA: Não foi possível acessar termux-battery-status", "ERROR")
            self.log("Solução:", "INFO")
            self.log("  1. Instalar: pkg install termux-api", "INFO")
            self.log("  2. Conceder permissões ao Termux no Android", "INFO")
            self.log("  3. Verificar se termux-api está rodando", "INFO")
            return False
        
        # 3. Validar dados da bateria
        percentage = battery_info.get("percentage", 0)
        if not isinstance(percentage, (int, float)) or percentage < 0 or percentage > 100:
            self.log(f"Dados de bateria inválidos: {percentage}%", "WARN")
            # Não é um erro fatal, mas registramos
        
        # 4. Testar envio de uma atualização
        self.log("Testando envio de atualização...", "DEBUG")
        test_data = {
            "percentage": percentage,
            "status": battery_info.get("status", "UNKNOWN"),
            "health": battery_info.get("health", "UNKNOWN"),
            "temperature": battery_info.get("temperature", 0)
        }
        
        success = self.send_battery_update(test_data)
        if not success:
            self.log("AVISO: Teste de envio falhou, mas continuando...", "WARN")
            # Não falhamos aqui porque pode ser um problema temporário
        
        # Resumo dos testes
        self.log("=" * 50, "INFO")
        self.log("✅ Testes de conexão concluídos", "INFO")
        self.log(f"  • Conexão com Core: OK", "INFO")
        self.log(f"  • API de bateria: OK ({percentage}%)", "INFO")
        self.log(f"  • Configurações:", "INFO")
        self.log(f"    - Intervalo: {self.poll_interval}s", "INFO")
        self.log(f"    - Limiar baixo: {self.low_battery_threshold}%", "INFO")
        self.log(f"    - Limiar crítico: {self.critical_battery_threshold}%", "INFO")
        self.log("=" * 50, "INFO")
        
        return True
    
    def run_monitoring_cycle(self) -> bool:
        """
        Executa um ciclo completo de monitoramento.
        
        Returns:
            True se o ciclo foi bem-sucedido, False caso contrário
        """
        try:
            # Obter informações atuais da bateria
            battery_info = self.get_battery_info()
            
            if not battery_info:
                self.consecutive_errors += 1
                
                if self.consecutive_errors >= self.max_consecutive_errors:
                    self.log(
                        f"Máximo de erros consecutivos atingido "
                        f"({self.consecutive_errors}/{self.max_consecutive_errors})",
                        "ERROR"
                    )
                    return False
                
                self.log(
                    f"Erro ao ler bateria "
                    f"({self.consecutive_errors}/{self.max_consecutive_errors})",
                    "WARN"
                )
                return True  # Continuar tentando
            
            # Resetar contador de erros em caso de sucesso
            self.consecutive_errors = 0
            
            # Verificar se houve mudança significativa
            if self.has_battery_changed(battery_info):
                # Enviar atualização para o Core
                success = self.send_battery_update(battery_info)
                
                if success:
                    # Atualizar estado local apenas se enviado com sucesso
                    self.update_local_state(battery_info)
                else:
                    self.log("Falha ao enviar atualização, mantendo estado anterior", "WARN")
            else:
                # Log silencioso apenas em modo debug
                if self.debug:
                    percentage = battery_info.get("percentage", 0)
                    self.log(f"Sem mudança significativa ({percentage}%)", "DEBUG")
            
            return True
            
        except Exception as e:
            self.log(f"Erro inesperado no ciclo de monitoramento: {e}", "ERROR")
            self.consecutive_errors += 1
            return self.consecutive_errors < self.max_consecutive_errors
    
    def run(self):
        """
        Loop principal de execução do agente.
        Implementação do método abstrato da classe base.
        """
        self.status = AgentStatus.RUNNING
        
        # Exibir banner informativo
        self.log("=" * 50, "INFO")
        self.log("🔋 Skuld Battery Agent v3.0", "INFO")
        self.log("=" * 50, "INFO")
        
        # Executar testes de conexão
        if not self.test_connections():
            self.log("Inicialização falhou. Corrija os problemas acima.", "ERROR")
            self.status = AgentStatus.ERROR
            return
        
        # Informações de inicialização bem-sucedida
        self.log("✅ Agente inicializado com sucesso!", "INFO")
        self.log(f"📊 Monitorando bateria a cada {self.poll_interval} segundos", "INFO")
        self.log("Pressione Ctrl+C para sair", "INFO")
        self.log("-" * 50, "INFO")
        
        # Loop principal de monitoramento
        cycle_count = 0
        
        try:
            while self.running and self.status == AgentStatus.RUNNING:
                cycle_count += 1
                
                if self.debug:
                    self.log(f"Ciclo de monitoramento #{cycle_count}", "DEBUG")
                
                # Executar ciclo de monitoramento
                continue_running = self.run_monitoring_cycle()
                
                if not continue_running:
                    self.log("Muitos erros consecutivos, encerrando...", "ERROR")
                    self.running = False
                    self.status = AgentStatus.ERROR
                    break
                
                # Aguardar próximo ciclo (com verificações periódicas)
                wait_start = time.time()
                while self.running and (time.time() - wait_start) < self.poll_interval:
                    time.sleep(0.5)  # Sleep curto para responsividade a sinais
            
        except KeyboardInterrupt:
            self.log("\nInterrompido pelo usuário via Ctrl+C", "INFO")
        except Exception as e:
            self.log(f"Erro inesperado no loop principal: {e}", "ERROR")
            self.status = AgentStatus.ERROR
        finally:
            # Limpeza final
            self.log(f"Total de ciclos executados: {cycle_count}", "INFO")
            self.log("Encerrando agente de bateria...", "INFO")
            self.status = AgentStatus.STOPPED
            self.log("=" * 50, "INFO")
    
    def start(self):
        """Inicia o agente (alias para run para compatibilidade)."""
        self.run()
    
    def stop(self):
        """Para o agente graciosamente."""
        self.running = False
        self.status = AgentStatus.STOPPING
        self.log("Solicitado desligamento do agente", "INFO")


def main():
    """Função principal com argumentos de linha de comando."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Skuld Battery Agent v3.0 - Monitora a bateria do Android',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  %(prog)s                    # Usa configurações padrão
  %(prog)s --interval 60      # Verifica a cada 60 segundos
  %(prog)s --socket /tmp/my.sock  # Usa socket personalizado
  %(prog)s --debug            # Ativa logs detalhados
  %(prog)s --threshold 25     # Alerta em 25%% em vez de 20%%
  %(prog)s --critical 10      # Crítico em 10%% em vez de 15%%

Configurações padrão:
  • Socket: /data/data/com.termux/files/usr/tmp/skuld.sock
  • Intervalo: 30 segundos
  • Limiar baixo: 20%%
  • Limiar crítico: 15%%
        """
    )
    
    parser.add_argument(
        '--socket',
        default='/data/data/com.termux/files/usr/tmp/skuld.sock',
        help='Caminho do socket UDS do Core (padrão: %(default)s)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        choices=range(10, 301, 10),  # 10 a 300 segundos, passos de 10
        help='Intervalo de verificação em segundos (10-300, padrão: %(default)s)'
    )
    
    parser.add_argument(
        '--threshold',
        type=int,
        default=20,
        choices=range(5, 51),  # 5 a 50%
        help='Limiar de bateria baixa em %% (5-50, padrão: %(default)s)'
    )
    
    parser.add_argument(
        '--critical',
        type=int,
        default=15,
        choices=range(1, 31),  # 1 a 30%
        help='Limiar de bateria crítica em %% (1-30, padrão: %(default)s)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Ativar modo debug com logs detalhados'
    )
    
    parser.add_argument(
        '--max-errors',
        type=int,
        default=3,
        help='Máximo de erros consecutivos antes de parar (padrão: %(default)s)'
    )
    
    args = parser.parse_args()
    
    # Criar e configurar o agente
    agent = BatteryAgent(
        socket_path=args.socket,
        debug=args.debug
    )
    
    # Aplicar configurações
    agent.poll_interval = args.interval
    agent.low_battery_threshold = args.threshold
    agent.critical_battery_threshold = args.critical
    agent.max_consecutive_errors = args.max_errors
    
    # Executar agente
    try:
        agent.run()
    except KeyboardInterrupt:
        agent.log("Agente interrompido", "INFO")
    except Exception as e:
        agent.log(f"Erro fatal: {e}", "ERROR")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
