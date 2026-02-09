#!/usr/bin/env python3
"""
Skuld Notifier Agent
Monitora o banco de dados por tarefas de notificação pendentes e executa-as.
"""

import json
import time
import sqlite3
import subprocess
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Adicionar o diretório common ao path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))
from agent_base import SkuldAgent, SkuldMessage


class NotifierAgent(SkuldAgent):
    """Agente que monitora e executa notificações pendentes"""
    
    def __init__(self, socket_path: str = None, agent_id: str = "notifier_agent"):
        super().__init__(socket_path, agent_id)
        
        # Configurações
        self.poll_interval = 10  # segundos
        self.db_path = os.path.expanduser("~/.skuld/skuld.db")
        self.running = True
        
        # Cache de notificações já processadas
        self.processed_notifications = set()
    
    def check_pending_notifications(self) -> list:
        """
        Verifica o banco por notificações pendentes
        Retorna lista de tarefas com status 'pending' e cmd 'notify_user'
        """
        tasks = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Buscar notificações pendentes
            cursor.execute("""
                SELECT id, params, timestamp, priority 
                FROM intentions 
                WHERE status = 'pending' 
                AND cmd = 'notify_user'
                ORDER BY priority ASC, timestamp ASC
                LIMIT 5
            """)
            
            for row in cursor.fetchall():
                task_id = row['id']
                
                # Evitar processar a mesma notificação várias vezes
                if task_id in self.processed_notifications:
                    continue
                
                try:
                    params = json.loads(row['params'])
                    tasks.append({
                        'id': task_id,
                        'params': params,
                        'timestamp': row['timestamp'],
                        'priority': row['priority']
                    })
                except json.JSONDecodeError:
                    self.log(f"Erro ao decodificar parâmetros da tarefa {task_id}")
            
            conn.close()
            
        except sqlite3.Error as e:
            self.log(f"Erro ao acessar banco de dados: {e}")
        
        return tasks
    
    def execute_notification(self, task: Dict[str, Any]) -> bool:
        """
        Executa uma notificação e atualiza o status no banco
        """
        task_id = task['id']
        params = task['params']
        
        try:
            # Enviar comando para o Core
            message = SkuldMessage(
                cmd="notify_user",
                agent=self.agent_id,
                priority=task['priority'],
                params=params
            )
            
            response = self.send_message(message)
            
            if response and response.get('status') == 'ok':
                self.log(f"✅ Notificação executada: {params.get('title', 'Sem título')}")
                
                # Marcar como processada localmente
                self.processed_notifications.add(task_id)
                
                # Podemos também enviar um comando para atualizar o status no Core
                # Mas o Core já atualiza automaticamente após processar
                return True
            else:
                error = response.get('error', 'Resposta inválida') if response else 'Sem resposta'
                self.log(f"❌ Erro ao executar notificação: {error}")
                return False
                
        except Exception as e:
            self.log(f"❌ Erro ao processar notificação {task_id}: {e}")
            return False
    
    def mark_task_completed(self, task_id: str):
        """
        Marca uma tarefa como concluída no cache local
        (O Core já faz isso, mas mantemos cache para evitar duplicatas)
        """
        self.processed_notifications.add(task_id)
        
        # Limitar tamanho do cache para evitar crescimento infinito
        if len(self.processed_notifications) > 100:
            # Manter apenas os 50 mais recentes (simplificado)
            self.processed_notifications = set(list(self.processed_notifications)[-50:])
    
    def run_monitoring_loop(self):
        """
        Loop principal de monitoramento
        """
        self.log(f"Iniciando monitor de notificações (intervalo: {self.poll_interval}s)")
        self.log(f"Banco de dados: {self.db_path}")
        
        while self.running:
            try:
                # Verificar notificações pendentes
                pending_tasks = self.check_pending_notifications()
                
                if pending_tasks:
                    self.log(f"📋 {len(pending_tasks)} notificação(ões) pendente(s)")
                    
                    # Processar cada tarefa
                    for task in pending_tasks:
                        if not self.running:
                            break
                        
                        success = self.execute_notification(task)
                        
                        if success:
                            self.mark_task_completed(task['id'])
                        
                        # Pequena pausa entre notificações
                        time.sleep(0.5)
                
                # Aguardar próximo ciclo
                for _ in range(self.poll_interval * 10):
                    if not self.running:
                        break
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                self.log("Interrupção por teclado recebida")
                self.running = False
                break
            except Exception as e:
                self.log(f"Erro no loop de monitoramento: {e}")
                time.sleep(5)  # Espera um pouco antes de tentar novamente
        
        self.log("Agente de notificações encerrado")
    
    def test_connection(self):
        """Testa a conexão com o Core e acesso ao banco"""
        self.log("Testando conexões...")
        
        # Testar conexão com Core
        if not self.test_core_connection():
            self.log("FALHA: Não foi possível conectar ao Core")
            return False
        
        # Testar acesso ao banco de dados
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            if tables:
                self.log(f"SUCESSO: Banco de dados acessível ({len(tables)} tabelas)")
                return True
            else:
                self.log("AVISO: Banco de dados vazio ou corrompido")
                return True  # Ainda pode funcionar, tabelas serão criadas
                
        except sqlite3.Error as e:
            self.log(f"FALHA: Não foi possível acessar o banco de dados: {e}")
            return False


def main():
    """Função principal para executar o agente de notificações"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Skuld Notifier Agent')
    parser.add_argument('--socket', default='/data/data/com.termux/files/usr/tmp/skuld.sock',
                       help='Caminho do socket UDS do Core')
    parser.add_argument('--interval', type=int, default=10,
                       help='Intervalo de verificação em segundos')
    parser.add_argument('--db-path', 
                       default='/data/data/com.termux/files/home/.skuld/skuld.db',
                       help='Caminho do banco de dados Skuld')
    parser.add_argument('--debug', action='store_true',
                       help='Ativar modo debug')
    
    args = parser.parse_args()
    
    # Criar e configurar o agente
    agent = NotifierAgent(
        socket_path=args.socket,
        agent_id="notifier_agent"
    )
    
    agent.poll_interval = args.interval
    agent.db_path = args.db_path
    agent.debug = args.debug
    
    # Exibir informações iniciais
    print("=" * 50)
    print("Skuld Notifier Agent")
    print("=" * 50)
    print(f"Socket: {args.socket}")
    print(f"Banco: {args.db_path}")
    print(f"Intervalo: {args.interval}s")
    print("=" * 50)
    
    # Testar conexões antes de iniciar
    if not agent.test_connection():
        print("\n[ERRO] Falha nos testes iniciais. Verifique:")
        print("1. O Skuld Core está rodando?")
        print("2. O banco de dados existe?")
        print("3. Permissões de leitura/escrita?")
        sys.exit(1)
    
    print("\n[OK] Testes passaram. Iniciando monitoramento...")
    print("Pressione Ctrl+C para parar\n")
    
    # Iniciar loop de monitoramento
    try:
        agent.run_monitoring_loop()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário")
    finally:
        print("Agente finalizado")


if __name__ == "__main__":
    main()
