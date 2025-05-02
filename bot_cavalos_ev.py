# BOT CAVALOS EV+ — MONITORAMENTO AUTOMÁTICO COM ODDSAPI + FAIR ODDS via ChatGPT
# Versão resumida com funções principais para deploy via Render

import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

ODDSAPI_KEY = os.getenv("ODDSAPI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EV_THRESHOLD = 0.05
CHECK_INTERVAL = 300

def get_odds_oddsapi():
    url = f"https://api.the-odds-api.com/v4/sports/horse_racing/odds/?apiKey={ODDSAPI_KEY}&regions=uk&markets=h2h&oddsFormat=decimal"
    try:
        res = requests.get(url)
        return res.json()
    except:
        return []

def calcular_ev(fair, atual):
    if fair <= 0 or atual <= 0:
        return -1
    prob_justa = 1 / fair
    return (prob_justa * atual) - 1

def solicitar_odd_justa_chatgpt(cavalo, corrida, odd_media):
    try:
        prompt = f"Projete a odd justa decimal para o cavalo '{cavalo}' na corrida '{corrida}'. A odd média de mercado é {odd_media:.2f}."

        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        resposta = response.json()['choices'][0]['message']['content']
        return float(resposta.strip())
    except:
        return odd_media

def enviar_alerta(cavalo, corrida, odd_bet365, fair_odd, ev):
    msg = f"""⚡ *APOSTA EV+ DETECTADA*

*Corrida:* {corrida}
*Cavalo:* {cavalo}
*Odd Bet365:* {odd_bet365:.2f}
*Odd Justa:* {fair_odd:.2f}
*EV:* {ev:.2%}
"""
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data=payload)

def monitorar_ev():
    dados = get_odds_oddsapi()
    corridas_processadas = set()
    for evento in dados:
        corrida_nome = evento.get('commence_time', '') + ' — ' + evento.get('home_team', '')
        mercado_bet365 = next((b for b in evento['bookmakers'] if b['title'] == 'Bet365'), None)
        if not mercado_bet365: continue
        mercados = mercado_bet365.get('markets', [])
        for mercado in mercados:
            for outcome in mercado.get('outcomes', []):
                cavalo = outcome['name']
                odd_bet365 = outcome['price']
                id_unico = f"{corrida_nome}-{cavalo}"
                if id_unico in corridas_processadas: continue
                corridas_processadas.add(id_unico)
                odd_justa = solicitar_odd_justa_chatgpt(cavalo, corrida_nome, odd_bet365)
                ev = calcular_ev(odd_justa, odd_bet365)
                if ev >= EV_THRESHOLD:
                    enviar_alerta(cavalo, corrida_nome, odd_bet365, odd_justa, ev)