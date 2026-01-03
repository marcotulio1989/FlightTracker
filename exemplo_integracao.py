#!/usr/bin/env python3
"""
Exemplo de integração do FlightMonitor com condições externas
(sua tabela, banco de dados, API, etc.)
"""

from flight_monitor_advanced import FlightMonitorAdvanced
from datetime import datetime, timezone, timedelta
import json

# Fuso horário de Brasília
BRASILIA_TZ = timezone(timedelta(hours=-3))


# =============================================================================
# EXEMPLO 1: Parar quando horário de chegada na sua tabela for preenchido
# =============================================================================

class MinhaTabela:
    """
    Simula sua tabela de voos.
    Substitua pelos seus dados reais (banco de dados, API, etc.)
    """
    
    def __init__(self):
        self.voos = {
            "PSCBJ": {
                "callsign": "PSCBJ",
                "horario_chegada": None,  # None = ainda não chegou
                "status": "em_voo"
            }
        }
    
    def get_voo(self, callsign: str) -> dict:
        """Retorna dados do voo."""
        return self.voos.get(callsign.upper(), {})
    
    def atualizar_horario_chegada(self, callsign: str, horario: str):
        """Atualiza horário de chegada."""
        if callsign.upper() in self.voos:
            self.voos[callsign.upper()]["horario_chegada"] = horario
            self.voos[callsign.upper()]["status"] = "pousado"
    
    def chegada_confirmada(self, callsign: str) -> bool:
        """Verifica se chegada foi confirmada."""
        voo = self.get_voo(callsign)
        return voo.get("horario_chegada") is not None


# Instância global da tabela (substitua pela sua conexão real)
tabela = MinhaTabela()


def monitorar_com_condicao_tabela(callsign: str, horario_programado: str):
    """
    Monitora voo e para quando a chegada for confirmada na tabela.
    """
    
    def verificar_chegada_tabela():
        """Condição: parar quando horário de chegada estiver preenchido."""
        return tabela.chegada_confirmada(callsign)
    
    monitor = FlightMonitorAdvanced(
        callsign=callsign,
        scheduled_time=horario_programado,
        minutes_before=15,
        check_interval_seconds=30,
        stop_on_change=False,  # Não para na mudança do FlightAware
        stop_condition=verificar_chegada_tabela,  # Para quando tabela atualizar
        max_duration_hours=4
    )
    
    return monitor.start()


# =============================================================================
# EXEMPLO 2: Atualizar sua tabela quando FlightMonitor detectar mudança
# =============================================================================

def monitorar_e_atualizar_tabela(callsign: str, horario_programado: str):
    """
    Monitora voo e atualiza a tabela quando detectar alteração.
    """
    
    monitor = FlightMonitorAdvanced(
        callsign=callsign,
        scheduled_time=horario_programado,
        minutes_before=15,
        check_interval_seconds=30,
        stop_on_change=True,  # Para quando detectar mudança
        max_duration_hours=4
    )
    
    result = monitor.start()
    
    # Quando detectar alteração, atualiza a tabela
    if result["status"] == "change_detected" and result["data"]:
        dados = result["data"]
        
        # Atualiza sua tabela com os dados do FlightAware
        if dados.get("landing") and dados.get("landing_type") == "actual":
            print(f"\n📝 Atualizando tabela com horário de chegada: {dados['landing']}")
            tabela.atualizar_horario_chegada(callsign, dados["landing"])
        
        # Salva log
        with open(f"log_{callsign}.json", "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"📄 Log salvo em log_{callsign}.json")
    
    return result


# =============================================================================
# EXEMPLO 3: Monitorar múltiplos voos ao mesmo tempo
# =============================================================================

import threading

def monitorar_multiplos_voos(voos: list):
    """
    Monitora múltiplos voos simultaneamente.
    
    Args:
        voos: Lista de dicionários com callsign e horario
              [{"callsign": "PSCBJ", "horario": "14:30"}, ...]
    """
    threads = []
    resultados = {}
    
    def monitorar_voo(callsign, horario):
        monitor = FlightMonitorAdvanced(
            callsign=callsign,
            scheduled_time=horario,
            minutes_before=15,
            check_interval_seconds=60,
            stop_on_change=True
        )
        resultados[callsign] = monitor.start()
    
    for voo in voos:
        t = threading.Thread(
            target=monitorar_voo,
            args=(voo["callsign"], voo["horario"])
        )
        threads.append(t)
        t.start()
    
    # Aguarda todos terminarem
    for t in threads:
        t.join()
    
    return resultados


# =============================================================================
# EXEMPLO 4: Uso como biblioteca (para integrar no seu app)
# =============================================================================

def usar_como_biblioteca():
    """Exemplo de uso como biblioteca."""
    
    # Cria monitor
    monitor = FlightMonitorAdvanced(
        callsign="PSCBJ",
        scheduled_time="14:30",
        minutes_before=15,
        check_interval_seconds=30,
        stop_on_change=True
    )
    
    # Inicia em background
    import threading
    
    resultado = {"data": None}
    
    def run_monitor():
        resultado["data"] = monitor.start()
    
    thread = threading.Thread(target=run_monitor)
    thread.start()
    
    # Você pode fazer outras coisas enquanto monitora...
    # ...
    
    # Para parar manualmente:
    # monitor.stop()
    
    # Ou aguarda terminar:
    thread.join()
    
    # Acessa os dados
    print("Dados finais:", resultado["data"])
    

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("📋 Exemplos de Integração do FlightMonitor")
    print("=" * 60)
    print()
    print("Escolha um exemplo:")
    print("1. Monitorar e parar quando tabela atualizar")
    print("2. Monitorar e atualizar tabela quando detectar mudança")
    print("3. Monitorar múltiplos voos")
    print("4. Sair")
    print()
    
    escolha = input("Opção: ").strip()
    
    if escolha == "1":
        callsign = input("Callsign: ").strip() or "PSCBJ"
        horario = input("Horário programado (HH:MM): ").strip() or "14:30"
        monitorar_com_condicao_tabela(callsign, horario)
        
    elif escolha == "2":
        callsign = input("Callsign: ").strip() or "PSCBJ"
        horario = input("Horário programado (HH:MM): ").strip() or "14:30"
        monitorar_e_atualizar_tabela(callsign, horario)
        
    elif escolha == "3":
        voos = [
            {"callsign": "PSCBJ", "horario": "14:30"},
            {"callsign": "PROHI", "horario": "15:00"}
        ]
        print("Monitorando:", voos)
        monitorar_multiplos_voos(voos)
        
    else:
        print("👋 Até logo!")
