#!/usr/bin/env python3
"""
FlightMonitor - Monitora voos em tempo real e alerta sobre alterações
Versão leve sem necessidade de Selenium
"""

import time
import json
import re
import requests
from datetime import datetime, timezone, timedelta

# Fuso horário de Brasília (UTC-3)
BRASILIA_TZ = timezone(timedelta(hours=-3))


class FlightMonitor:
    """Monitor de voos em tempo real."""
    
    def __init__(self, callsign: str, duration_hours: float = 3, check_interval_seconds: int = 60):
        """
        Inicializa o monitor.
        
        Args:
            callsign: Callsign da aeronave (ex: PSCBJ)
            duration_hours: Duração do monitoramento em horas
            check_interval_seconds: Intervalo entre verificações em segundos
        """
        self.callsign = callsign.upper()
        self.url = f"https://www.flightaware.com/live/flight/{self.callsign}"
        self.duration_seconds = int(duration_hours * 3600)
        self.check_interval = check_interval_seconds
        self.last_data = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def _extract_flight_data(self) -> dict:
        """Extrai dados do voo da página."""
        data = {
            "timestamp": datetime.now(BRASILIA_TZ).strftime("%H:%M:%S"),
            "takeoff": None,
            "takeoff_scheduled": None,
            "landing": None,
            "landing_scheduled": None,
            "status": None,
            "origin": None,
            "destination": None,
            "aircraft": None
        }
        
        try:
            response = requests.get(self.url, headers=self.headers, timeout=15)
            response.raise_for_status()
            html = response.text
            
            # Procura pelo trackpollBootstrap no JavaScript
            match = re.search(r'var\s+trackpollBootstrap\s*=\s*(\{.*?\});', html, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    bootstrap_data = json.loads(json_str)
                    
                    if 'flights' in bootstrap_data:
                        for flight_id, flight_data in bootstrap_data['flights'].items():
                            # Takeoff
                            if 'takeoffTimes' in flight_data:
                                takeoff = flight_data['takeoffTimes']
                                if 'actual' in takeoff:
                                    ts = takeoff['actual']
                                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(BRASILIA_TZ)
                                    data["takeoff"] = dt.strftime("%H:%M")
                                if 'scheduled' in takeoff:
                                    ts = takeoff['scheduled']
                                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(BRASILIA_TZ)
                                    data["takeoff_scheduled"] = dt.strftime("%H:%M")
                            
                            # Landing
                            if 'landingTimes' in flight_data:
                                landing = flight_data['landingTimes']
                                if 'actual' in landing:
                                    ts = landing['actual']
                                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(BRASILIA_TZ)
                                    data["landing"] = dt.strftime("%H:%M")
                                    data["landing_type"] = "actual"
                                elif 'estimated' in landing:
                                    ts = landing['estimated']
                                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(BRASILIA_TZ)
                                    data["landing"] = dt.strftime("%H:%M")
                                    data["landing_type"] = "estimated"
                                if 'scheduled' in landing:
                                    ts = landing['scheduled']
                                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(BRASILIA_TZ)
                                    data["landing_scheduled"] = dt.strftime("%H:%M")
                            
                            # Origem e destino
                            if 'origin' in flight_data:
                                origin = flight_data['origin']
                                data["origin"] = origin.get('friendlyName', origin.get('icao', ''))
                            if 'destination' in flight_data:
                                dest = flight_data['destination']
                                data["destination"] = dest.get('friendlyName', dest.get('icao', ''))
                            
                            # Aeronave
                            if 'aircraft' in flight_data:
                                aircraft = flight_data['aircraft']
                                data["aircraft"] = aircraft.get('friendlyType', aircraft.get('type', ''))
                            
                            # Status do voo
                            if 'flightStatus' in flight_data:
                                data["status"] = flight_data['flightStatus']
                            
                            break
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    data["parse_error"] = str(e)
                    
        except requests.RequestException as e:
            data["error"] = str(e)
            
        return data
    
    def _compare_data(self, old_data: dict, new_data: dict) -> list:
        """Compara dados e retorna lista de mudanças."""
        changes = []
        
        if old_data is None:
            return changes
            
        fields_to_compare = [
            ("takeoff", "🛫 Takeoff"),
            ("takeoff_scheduled", "📅 Takeoff Programado"),
            ("landing", "🛬 Landing"),
            ("landing_scheduled", "📅 Landing Programado"),
            ("status", "📊 Status"),
            ("origin", "🏁 Origem"),
            ("destination", "🎯 Destino")
        ]
        
        for field, field_name in fields_to_compare:
            old_val = old_data.get(field)
            new_val = new_data.get(field)
            
            if old_val != new_val and new_val is not None:
                changes.append({
                    "field": field,
                    "field_name": field_name,
                    "old": old_val or "N/A",
                    "new": new_val
                })
                
        return changes
    
    def _print_alert(self, changes: list):
        """Imprime alerta de mudança."""
        print("\n" + "🚨" * 25)
        print(f"⚠️  ALTERAÇÃO DETECTADA às {datetime.now(BRASILIA_TZ).strftime('%H:%M:%S')} (Brasília)!")
        print("🚨" * 25)
        
        for change in changes:
            print(f"  {change['field_name']}: {change['old']} → {change['new']}")
        
        print("🚨" * 25 + "\n")
    
    def _format_landing(self, data: dict) -> str:
        """Formata o horário de landing com tipo."""
        landing = data.get('landing')
        if not landing:
            return "N/A"
        
        landing_type = data.get('landing_type', '')
        if landing_type == 'estimated':
            return f"{landing} (est)"
        return landing
    
    def _print_status(self, data: dict, check_count: int):
        """Imprime status atual."""
        now = datetime.now(BRASILIA_TZ).strftime("%H:%M:%S")
        takeoff = data.get('takeoff') or 'N/A'
        landing = self._format_landing(data)
        status = data.get('status') or 'N/A'
        
        print(f"[{now}] #{check_count:03d} | 🛫 {takeoff} | 🛬 {landing} | Status: {status}")
    
    def _print_initial_info(self, data: dict):
        """Imprime informações iniciais do voo."""
        print("\n📋 Informações do Voo:")
        print("-" * 50)
        print(f"   ✈️  Aeronave:  {data.get('aircraft') or 'N/A'}")
        print(f"   🏁 Origem:    {data.get('origin') or 'N/A'}")
        print(f"   🎯 Destino:   {data.get('destination') or 'N/A'}")
        print(f"   🛫 Takeoff:   {data.get('takeoff') or 'N/A'} (Programado: {data.get('takeoff_scheduled') or 'N/A'})")
        print(f"   🛬 Landing:   {self._format_landing(data)} (Programado: {data.get('landing_scheduled') or 'N/A'})")
        print(f"   📊 Status:    {data.get('status') or 'N/A'}")
        print("-" * 50)
        print()
    
    def start(self):
        """Inicia o monitoramento."""
        print("\n" + "=" * 60)
        print("🔍 FlightMonitor - Monitoramento em Tempo Real")
        print("=" * 60)
        print(f"✈️  Aeronave:   {self.callsign}")
        print(f"🔗 URL:        {self.url}")
        print(f"⏱️  Duração:    {self.duration_seconds / 3600:.1f} horas")
        print(f"🔄 Intervalo:  {self.check_interval} segundos")
        print("=" * 60)
        
        print("\n📡 Buscando dados iniciais...")
        
        start_time = time.time()
        check_count = 0
        changes_detected = 0
        
        # Primeira leitura
        current_data = self._extract_flight_data()
        check_count += 1
        
        if current_data.get("error"):
            print(f"❌ Erro ao acessar: {current_data['error']}")
            return
        
        self._print_initial_info(current_data)
        self.last_data = current_data
        
        print("📊 Monitoramento iniciado! Pressione Ctrl+C para parar.\n")
        print("-" * 60)
        self._print_status(current_data, check_count)
        
        try:
            while (time.time() - start_time) < self.duration_seconds:
                # Aguarda próxima verificação
                remaining = self.duration_seconds - (time.time() - start_time)
                if remaining <= 0:
                    break
                    
                time.sleep(min(self.check_interval, remaining))
                
                check_count += 1
                
                # Busca novos dados
                current_data = self._extract_flight_data()
                
                if current_data.get("error"):
                    now = datetime.now(BRASILIA_TZ).strftime("%H:%M:%S")
                    print(f"[{now}] ⚠️  Erro na requisição: {current_data['error']}")
                    continue
                
                # Verifica mudanças
                changes = self._compare_data(self.last_data, current_data)
                if changes:
                    changes_detected += 1
                    self._print_alert(changes)
                
                # Mostra status atual
                self._print_status(current_data, check_count)
                
                # Salva dados para comparação
                self.last_data = current_data
                    
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoramento interrompido pelo usuário.")
        
        # Resumo final
        print("\n" + "=" * 60)
        print("📊 RESUMO DO MONITORAMENTO")
        print("=" * 60)
        print(f"   ⏱️  Duração total:     {(time.time() - start_time) / 60:.1f} minutos")
        print(f"   🔄 Verificações:      {check_count}")
        print(f"   🚨 Alterações:        {changes_detected}")
        print("=" * 60)
        print("✅ Monitoramento finalizado!")


def main():
    """Função principal."""
    print("\n" + "=" * 60)
    print("🛫 FlightMonitor - Monitoramento de Voos em Tempo Real 🛬")
    print("=" * 60)
    print()
    
    callsign = input("Digite o callsign da aeronave: ").strip()
    if not callsign:
        print("❌ Callsign inválido!")
        return
    
    try:
        hours_input = input("Duração do monitoramento em horas [padrão: 3]: ").strip()
        hours = float(hours_input) if hours_input else 3
    except ValueError:
        hours = 3
    
    try:
        interval_input = input("Intervalo entre verificações em segundos [padrão: 60]: ").strip()
        interval = int(interval_input) if interval_input else 60
    except ValueError:
        interval = 60
    
    monitor = FlightMonitor(callsign, duration_hours=hours, check_interval_seconds=interval)
    monitor.start()


if __name__ == "__main__":
    main()
