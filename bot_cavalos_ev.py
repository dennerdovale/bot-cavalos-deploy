# BOT CAVALOS EV+ — MONITORAMENTO AUTOMÁTICO COM ODDSAPI + FAIR ODDS via ChatGPT

import requests
import time
import os
from statistics import mean
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# === CONFIGURAÇÕES ===
ODDSAPI_KEY = os.getenv("ODDSAPI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EV_THRESHOLD = 0.05  # valor mínimo de EV para alertar
CHECK_INTERVAL = 300  # checagem a cada 5 minutos

# === FUNÇÕES ===
def enviar_log_erro(mensagem):
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': f"⚠️ [ERRO] {mensagem}",
        'parse_mode': 'Markdown'
    }
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data=payload)
    except:
        pass

def get_odds_oddsapi():
    url = f"https://api.the-odds-api.com/v4/sports/horse_racing/odds/?apiKey={ODDSAPI_KEY}&regions=uk&markets=h2h&oddsFormat=decimal"
    try:
        res = requests.get(url)
        return res.json()
    except Exception as e:
        erro = f"API ODDSAPI: {e}"
        print(f"[ERRO] {erro}")
        enviar_log_erro(erro)
        return []

def calcular_ev(fair, atual):
    if fair <= 0 or atual <= 0:
        return -1
    prob_justa = 1 / fair
    return (prob_justa * atual) - 1

def enviar_alerta(cavalo, corrida, odd_bet365, fair_odd, ev):
    msg = f"\u26a1 *APOSTA EV+ DETECTADA*\n\n" \
          f"*Corrida:* {corrida}\n" \
          f"*Cavalo:* {cavalo}\n" \
          f"*Odd Bet365:* {odd_bet365:.2f}\n" \
          f"*Odd Justa:* {fair_odd:.2f}\n" \
          f"*EV:* {ev:.2%}"

    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': msg,
        'parse_mode': 'Markdown'
    }
    tentativas = 0
    while tentativas < 3:
        try:
            resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data=payload)
            if resp.status_code != 200:
                print(f"[ERRO TELEGRAM] {resp.status_code} - {resp.text}")
                enviar_log_erro(f"Falha no Telegram: {resp.text}")
            else:
                print("[INFO] Mensagem enviada com sucesso.")
                break
        except Exception as e:
            erro = f"TELEGRAM ALERTA (tentativa {tentativas + 1}): {e}"
            print(f"[ERRO] {erro}")
            enviar_log_erro(erro)
            time.sleep(5)
            tentativas += 1

def solicitar_odd_justa_chatgpt(cavalo, corrida, odd_media):
    try:
        prompt = f"Projete a odd justa decimal para o cavalo '{cavalo}' na corrida '{corrida}'. A odd média de mercado é {odd_media:.2f}. Considere forma, draw, treinador, jóquei e estilo de corrida. Responda com apenas o número decimal da odd justa."

        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        data = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        resposta = response.json()['choices'][0]['message']['content']
        return float(resposta.strip())

    except Exception as e:
        erro = f"CHATGPT PRECIFICAÇÃO: {e}"
        print(f"[ERRO] {erro}")
        enviar_log_erro(erro)
        return round(odd_media, 2)

def monitorar_ev():
    dados = get_odds_oddsapi()
    corridas_processadas = set()

    for evento in dados:
        if 'bookmakers' not in evento:
            continue

        corrida_nome = evento.get('commence_time', '') + ' — ' + evento.get('home_team', '')
        mercado_bet365 = next((b for b in evento['bookmakers'] if b['title'] == 'Bet365'), None)
        if not mercado_bet365:
            continue

        mercados = mercado_bet365.get('markets', [])
        for mercado in mercados:
            for outcome in mercado.get('outcomes', []):
                cavalo = outcome['name']
                odd_bet365 = outcome['price']

                id_unico = f"{corrida_nome}-{cavalo}"
                if id_unico in corridas_processadas:
                    continue
                corridas_processadas.add(id_unico)

                odd_media = odd_bet365  # placeholder
                odd_justa = solicitar_odd_justa_chatgpt(cavalo, corrida_nome, odd_media)
                ev = calcular_ev(odd_justa, odd_bet365)

                if ev >= EV_THRESHOLD:
                    enviar_alerta(cavalo, corrida_nome, odd_bet365, odd_justa, ev)

if __name__ == '__main__':
    while True:
        monitorar_ev()
        time.sleep(CHECK_INTERVAL)
