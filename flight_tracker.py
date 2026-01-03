#!/usr/bin/env python3
"""
FlightTracker - Extrai horários de voo do FlightAware
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime, timezone, timedelta

# Fuso horário de Brasília (UTC-3)
BRASILIA_TZ = timezone(timedelta(hours=-3))


def get_flight_times(callsign: str) -> dict:
    """
    Busca os horários de voo de uma aeronave pelo callsign.
    
    Args:
        callsign: O callsign da aeronave (ex: PROHI, PSCBJ)
    
    Returns:
        Dicionário com os horários de takeoff e landing
    """
    url = f"https://www.flightaware.com/live/flight/{callsign.upper()}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"Erro ao acessar o site: {e}"}
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Procura pela tabela de Flight Times
    flight_times = {
        "callsign": callsign.upper(),
        "url": url,
        "takeoff": {
            "actual": None,
            "scheduled": None
        },
        "landing": {
            "actual": None,
            "scheduled": None
        }
    }
    
    # Tenta extrair dados do JSON embutido na página (trackpollBootstrap)
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'trackpollBootstrap' in str(script.string):
            text = script.string
            
            # Procura pelo objeto trackpollBootstrap
            match = re.search(r'var\s+trackpollBootstrap\s*=\s*(\{.*?\});', text, re.DOTALL)
            if match:
                try:
                    # Limpa e parseia o JSON
                    json_str = match.group(1)
                    # Remove funções JavaScript que podem estar no objeto
                    json_str = re.sub(r',\s*\w+:\s*function\s*\([^)]*\)\s*\{[^}]*\}', '', json_str)
                    data = json.loads(json_str)
                    
                    if 'flights' in data:
                        for flight_id, flight_data in data['flights'].items():
                            # Extrai horários de takeoff
                            if 'takeoffTimes' in flight_data:
                                takeoff = flight_data['takeoffTimes']
                                if 'actual' in takeoff:
                                    flight_times["takeoff"]["actual_timestamp"] = takeoff['actual']
                                if 'scheduled' in takeoff:
                                    flight_times["takeoff"]["scheduled_timestamp"] = takeoff['scheduled']
                            
                            # Extrai horários de landing
                            if 'landingTimes' in flight_data:
                                landing = flight_data['landingTimes']
                                if 'actual' in landing:
                                    flight_times["landing"]["actual_timestamp"] = landing['actual']
                                if 'estimated' in landing:
                                    flight_times["landing"]["estimated_timestamp"] = landing['estimated']
                                if 'scheduled' in landing:
                                    flight_times["landing"]["scheduled_timestamp"] = landing['scheduled']
                            
                            # Pega o primeiro voo apenas
                            break
                except (json.JSONDecodeError, KeyError):
                    pass
    
    # Procura pelos elementos na página renderizada
    # Classe flightPageDataTableContainer contém os Flight Times
    containers = soup.find_all('div', class_='flightPageDataTableContainer')
    
    for container in containers:
        text = container.get_text()
        if 'Flight Times' in text or 'Takeoff' in text:
            # Encontra os elementos com horários
            time_elements = container.find_all('span', class_='flightPageSummaryDeparture')
            for elem in time_elements:
                if elem.get_text(strip=True):
                    flight_times["takeoff"]["actual"] = elem.get_text(strip=True)
            
            time_elements = container.find_all('span', class_='flightPageSummaryArrival')
            for elem in time_elements:
                if elem.get_text(strip=True):
                    flight_times["landing"]["actual"] = elem.get_text(strip=True)
    
    # Procura diretamente na estrutura de summary
    departure_span = soup.find('span', class_='flightPageSummaryDeparture')
    if departure_span:
        flight_times["takeoff"]["actual"] = departure_span.get_text(strip=True)
    
    arrival_span = soup.find('span', class_='flightPageSummaryArrival')
    if arrival_span:
        flight_times["landing"]["actual"] = arrival_span.get_text(strip=True)
    
    # Extrai origem e destino
    origin = soup.find('div', class_='flightPageSummaryOrigin')
    if origin:
        airport_code = origin.find('span', class_='flightPageSummaryAirportCode')
        if airport_code:
            flight_times["origin"] = airport_code.get_text(strip=True)
    
    destination = soup.find('div', class_='flightPageSummaryDestination')
    if destination:
        airport_code = destination.find('span', class_='flightPageSummaryAirportCode')
        if airport_code:
            flight_times["destination"] = airport_code.get_text(strip=True)
    
    return flight_times


def main():
    """Função principal do aplicativo."""
    print("=" * 50)
    print("🛫 FlightTracker - Rastreador de Voos 🛬")
    print("=" * 50)
    print()
    
    while True:
        callsign = input("Digite o callsign da aeronave (ou 'sair' para encerrar): ").strip()
        
        if callsign.lower() == 'sair':
            print("\n👋 Até logo!")
            break
        
        if not callsign:
            print("⚠️  Por favor, digite um callsign válido.\n")
            continue
        
        print(f"\n🔍 Buscando informações para: {callsign.upper()}")
        print(f"📡 URL: https://www.flightaware.com/live/flight/{callsign.upper()}\n")
        
        result = get_flight_times(callsign)
        
        if "error" in result:
            print(f"❌ {result['error']}\n")
        else:
            print("✈️  Informações do Voo:")
            print("-" * 40)
            
            if result.get("origin"):
                print(f"🛫 Origem:   {result['origin']}")
            if result.get("destination"):
                print(f"🛬 Destino:  {result['destination']}")
            
            print()
            print("⏰ Horários:")
            print("-" * 40)
            
            # Takeoff
            takeoff_info = result.get("takeoff", {})
            if takeoff_info.get("actual"):
                print(f"🛫 Takeoff:  {takeoff_info['actual']}")
            elif takeoff_info.get("actual_timestamp"):
                ts = int(takeoff_info['actual_timestamp'])
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(BRASILIA_TZ)
                print(f"🛫 Takeoff:  {dt.strftime('%H:%M')} (horário de Brasília)")
            else:
                print("🛫 Takeoff:  Não disponível")
            
            # Landing
            landing_info = result.get("landing", {})
            if landing_info.get("actual"):
                print(f"🛬 Landing:  {landing_info['actual']}")
            elif landing_info.get("actual_timestamp"):
                ts = int(landing_info['actual_timestamp'])
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(BRASILIA_TZ)
                print(f"🛬 Landing:  {dt.strftime('%H:%M')} (horário de Brasília)")
            elif landing_info.get("estimated_timestamp"):
                ts = int(landing_info['estimated_timestamp'])
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(BRASILIA_TZ)
                print(f"🛬 Landing:  {dt.strftime('%H:%M')} (estimado - horário de Brasília)")
            else:
                print("🛬 Landing:  Não disponível")
            
            print("-" * 40)
        
        print()


if __name__ == "__main__":
    main()
