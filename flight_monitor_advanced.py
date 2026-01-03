#!/usr/bin/env python3
"""
FlightMonitor Avançado - Monitora voos com agendamento e condições de parada
"""

import time
import json
import re
import requests
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional
import threading

# Fuso horário de Brasília (UTC-3)
BRASILIA_TZ = timezone(timedelta(hours=-3))


class FlightMonitorAdvanced:
    """Monitor avançado de voos com agendamento e condições de parada."""
    
    def __init__(
        self,
        callsign: str,
        scheduled_time: str,  # Horário programado do voo (HH:MM)
        minutes_before: int = 15,
        check_interval_seconds: int = 30,
        stop_on_change: bool = True,
        stop_condition: Optional[Callable[[], bool]] = None,
        max_duration_hours: float = 4
    ):
        """
        Inicializa o monitor.
        
        Args:
            callsign: Callsign da aeronave (ex: PSCBJ)
            scheduled_time: Horário programado do voo no formato HH:MM
            minutes_before: Minutos antes do horário para começar a monitorar
            check_interval_seconds: Intervalo entre verificações em segundos
            stop_on_change: Se True, para quando detectar alteração
            stop_condition: Função externa que retorna True para parar o monitoramento
            max_duration_hours: Duração máxima do monitoramento em horas
        """
        self.callsign = callsign.upper()
        self.url = f"https://www.flightaware.com/live/flight/{self.callsign}"
        self.scheduled_time = scheduled_time
        self.minutes_before = minutes_before
        self.check_interval = check_interval_seconds
        self.stop_on_change = stop_on_change
        self.stop_condition = stop_condition
        self.max_duration_seconds = int(max_duration_hours * 3600)
        self.last_data = None
        self.changes_log = []
        self.is_running = False
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
    def _parse_time(self, time_str: str) -> datetime:
        """Converte string HH:MM para datetime de hoje."""
        hour, minute = map(int, time_str.split(':'))
        now = datetime.now(BRASILIA_TZ)
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Calcula o horário de início (com antecedência)
        start_time = scheduled - timedelta(minutes=self.minutes_before)
        
        # Se o horário de início já passou, retorna o horário de hoje mesmo
        # (o método _wait_until_start vai detectar e iniciar imediatamente)
        # Só agenda para amanhã se o horário de INÍCIO ainda não chegou
        if start_time < now and (now - start_time).total_seconds() > 60:
            # Horário já passou há mais de 1 minuto, agenda para amanhã
            scheduled += timedelta(days=1)
            
        return scheduled
    
    def _wait_until_start(self) -> bool:
        """Aguarda até o momento de iniciar o monitoramento."""
        now = datetime.now(BRASILIA_TZ)
        
        # Parse do horário programado
        hour, minute = map(int, self.scheduled_time.split(':'))
        scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Horário de início = horário programado - minutos de antecedência
        start_time = scheduled_today - timedelta(minutes=self.minutes_before)
        
        # Se o horário de início já passou (mesmo que seja de hoje), começa imediatamente
        if now >= start_time:
            print(f"✅ Iniciando monitoramento imediatamente...")
            return True
        
        # Senão, aguarda
        wait_seconds = (start_time - now).total_seconds()
        
        print(f"\n⏰ Horário programado do voo: {self.scheduled_time}")
        print(f"🕐 Início do monitoramento:   {start_time.strftime('%H:%M:%S')} ({self.minutes_before} min antes)")
        print(f"⏳ Aguardando {wait_seconds/60:.1f} minutos para iniciar...")
        print(f"   (Pressione Ctrl+C para cancelar)\n")
        
        try:
            # Mostra countdown
            while datetime.now(BRASILIA_TZ) < start_time:
                remaining = (start_time - datetime.now(BRASILIA_TZ)).total_seconds()
                mins, secs = divmod(int(remaining), 60)
                hours, mins = divmod(mins, 60)
                
                if hours > 0:
                    print(f"\r   ⏳ Faltam {hours:02d}:{mins:02d}:{secs:02d} para iniciar...", end="", flush=True)
                else:
                    print(f"\r   ⏳ Faltam {mins:02d}:{secs:02d} para iniciar...     ", end="", flush=True)
                
                time.sleep(1)
                
            print("\n")
            return True
            
        except KeyboardInterrupt:
            print("\n\n❌ Agendamento cancelado pelo usuário.")
            return False
        
    def _extract_flight_data(self) -> dict:
        """Extrai dados do voo da página."""
        data = {
            "timestamp": datetime.now(BRASILIA_TZ).strftime("%H:%M:%S"),
            "takeoff": None,
            "takeoff_scheduled": None,
            "landing": None,
            "landing_scheduled": None,
            "landing_type": None,
            "status": None,
            "origin": None,
            "destination": None,
            "aircraft": None,
            "flight_id": None
        }
        
        try:
            response = requests.get(self.url, headers=self.headers, timeout=15)
            response.raise_for_status()
            html = response.text
            
            match = re.search(r'var\s+trackpollBootstrap\s*=\s*(\{.*?\});', html, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    bootstrap_data = json.loads(json_str)
                    
                    if 'flights' in bootstrap_data:
                        for flight_id, flight_data in bootstrap_data['flights'].items():
                            data["flight_id"] = flight_id
                            
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
                            
                            # Status
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
            ("status", "📊 Status")
        ]
        
        for field, field_name in fields_to_compare:
            old_val = old_data.get(field)
            new_val = new_data.get(field)
            
            if old_val != new_val and new_val is not None:
                changes.append({
                    "field": field,
                    "field_name": field_name,
                    "old": old_val or "N/A",
                    "new": new_val,
                    "timestamp": datetime.now(BRASILIA_TZ).strftime("%H:%M:%S")
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
        print("-" * 55)
        print(f"   ✈️  Aeronave:  {data.get('aircraft') or 'N/A'}")
        print(f"   🏁 Origem:    {data.get('origin') or 'N/A'}")
        print(f"   🎯 Destino:   {data.get('destination') or 'N/A'}")
        print(f"   🛫 Takeoff:   {data.get('takeoff') or 'N/A'} (Prog: {data.get('takeoff_scheduled') or 'N/A'})")
        print(f"   🛬 Landing:   {self._format_landing(data)} (Prog: {data.get('landing_scheduled') or 'N/A'})")
        print(f"   📊 Status:    {data.get('status') or 'N/A'}")
        print("-" * 55)
    
    def get_last_data(self) -> dict:
        """Retorna os últimos dados coletados."""
        return self.last_data
    
    def get_changes_log(self) -> list:
        """Retorna log de todas as alterações detectadas."""
        return self.changes_log
    
    def stop(self):
        """Para o monitoramento."""
        self.is_running = False
    
    def start(self) -> dict:
        """
        Inicia o monitoramento.
        
        Returns:
            Dicionário com dados finais e log de alterações
        """
        print("\n" + "=" * 60)
        print("🔍 FlightMonitor Avançado - Monitoramento Agendado")
        print("=" * 60)
        print(f"✈️  Aeronave:      {self.callsign}")
        print(f"🔗 URL:           {self.url}")
        print(f"⏰ Horário voo:   {self.scheduled_time}")
        print(f"🕐 Início:        {self.minutes_before} min antes")
        print(f"🔄 Intervalo:     {self.check_interval} segundos")
        print(f"🛑 Parar na mudança: {'Sim' if self.stop_on_change else 'Não'}")
        print(f"⏱️  Duração máx:   {self.max_duration_seconds / 3600:.1f} horas")
        print("=" * 60)
        
        # Aguarda horário de início
        if not self._wait_until_start():
            return {"status": "cancelled", "data": None, "changes": []}
        
        print("🚀 Iniciando monitoramento...")
        self.is_running = True
        
        start_time = time.time()
        check_count = 0
        
        # Primeira leitura
        current_data = self._extract_flight_data()
        check_count += 1
        
        if current_data.get("error"):
            print(f"❌ Erro ao acessar: {current_data['error']}")
            return {"status": "error", "data": current_data, "changes": []}
        
        self._print_initial_info(current_data)
        self.last_data = current_data
        
        print("\n📊 Monitorando... Pressione Ctrl+C para parar.\n")
        print("-" * 60)
        self._print_status(current_data, check_count)
        
        stop_reason = "timeout"
        
        try:
            while self.is_running and (time.time() - start_time) < self.max_duration_seconds:
                
                # Verifica condição externa de parada
                if self.stop_condition and self.stop_condition():
                    print("\n\n✅ Condição externa atendida! Parando monitoramento...")
                    stop_reason = "condition_met"
                    break
                
                # Aguarda próxima verificação
                remaining = self.max_duration_seconds - (time.time() - start_time)
                if remaining <= 0:
                    break
                    
                time.sleep(min(self.check_interval, remaining))
                
                if not self.is_running:
                    stop_reason = "stopped"
                    break
                
                check_count += 1
                
                # Busca novos dados
                current_data = self._extract_flight_data()
                
                if current_data.get("error"):
                    now = datetime.now(BRASILIA_TZ).strftime("%H:%M:%S")
                    print(f"[{now}] ⚠️  Erro: {current_data['error']}")
                    continue
                
                # Verifica mudanças
                changes = self._compare_data(self.last_data, current_data)
                if changes:
                    self.changes_log.extend(changes)
                    self._print_alert(changes)
                    
                    if self.stop_on_change:
                        print("✅ Alteração detectada! Parando monitoramento...")
                        stop_reason = "change_detected"
                        self.last_data = current_data
                        break
                
                # Mostra status atual
                self._print_status(current_data, check_count)
                
                # Salva dados
                self.last_data = current_data
                    
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoramento interrompido pelo usuário.")
            stop_reason = "user_interrupt"
        
        self.is_running = False
        
        # Resumo final
        duration = time.time() - start_time
        print("\n" + "=" * 60)
        print("📊 RESUMO DO MONITORAMENTO")
        print("=" * 60)
        print(f"   ⏱️  Duração:        {duration / 60:.1f} minutos")
        print(f"   🔄 Verificações:   {check_count}")
        print(f"   🚨 Alterações:     {len(self.changes_log)}")
        print(f"   🛑 Motivo parada:  {stop_reason}")
        print("=" * 60)
        
        if self.last_data:
            print("\n📋 Dados Finais:")
            self._print_initial_info(self.last_data)
        
        print("\n✅ Monitoramento finalizado!")
        
        return {
            "status": stop_reason,
            "data": self.last_data,
            "changes": self.changes_log,
            "duration_seconds": duration,
            "total_checks": check_count
        }


def main():
    """Função principal interativa."""
    print("\n" + "=" * 60)
    print("🛫 FlightMonitor Avançado - Monitoramento Agendado 🛬")
    print("=" * 60)
    print()
    
    callsign = input("Digite o callsign da aeronave: ").strip()
    if not callsign:
        print("❌ Callsign inválido!")
        return
    
    scheduled_time = input("Horário programado do voo (HH:MM): ").strip()
    if not scheduled_time or ':' not in scheduled_time:
        print("❌ Horário inválido! Use o formato HH:MM")
        return
    
    try:
        minutes_input = input("Minutos antes para iniciar monitoramento [padrão: 15]: ").strip()
        minutes_before = int(minutes_input) if minutes_input else 15
    except ValueError:
        minutes_before = 15
    
    try:
        interval_input = input("Intervalo entre verificações em segundos [padrão: 30]: ").strip()
        interval = int(interval_input) if interval_input else 30
    except ValueError:
        interval = 30
    
    stop_input = input("Parar ao detectar alteração? [S/n]: ").strip().lower()
    stop_on_change = stop_input != 'n'
    
    try:
        max_hours_input = input("Duração máxima em horas [padrão: 4]: ").strip()
        max_hours = float(max_hours_input) if max_hours_input else 4
    except ValueError:
        max_hours = 4
    
    # Exemplo de condição externa (pode ser substituída pela sua lógica)
    # Por exemplo, verificar se existe um registro em uma tabela
    def check_external_condition():
        """
        Sua condição externa aqui.
        Retorne True para parar o monitoramento.
        
        Exemplos:
        - Verificar se registro existe no banco
        - Verificar se arquivo foi criado
        - Verificar resposta de uma API
        """
        # Exemplo: verificar se existe um arquivo de flag
        # import os
        # return os.path.exists('/tmp/stop_monitoring.flag')
        return False
    
    monitor = FlightMonitorAdvanced(
        callsign=callsign,
        scheduled_time=scheduled_time,
        minutes_before=minutes_before,
        check_interval_seconds=interval,
        stop_on_change=stop_on_change,
        stop_condition=check_external_condition,
        max_duration_hours=max_hours
    )
    
    result = monitor.start()
    
    # Retorna os dados para uso externo
    print("\n📤 Dados disponíveis em 'result' para integração")
    return result


if __name__ == "__main__":
    result = main()
