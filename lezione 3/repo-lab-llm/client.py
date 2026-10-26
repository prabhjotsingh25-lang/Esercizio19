"""Client minimo per il server locale di LM Studio.

Scheletro da completare con Claude Code (slide 19-22):
configurazione, messaggi, payload e chiamata HTTP.
Import e gestione degli errori sono gia' presenti: conservarli.
"""

import os

import requests
from dotenv import load_dotenv

# --- Configurazione -------------------------------------------------------
load_dotenv()
base_url = os.getenv("LM_BASE_URL")
model = os.getenv("LM_MODEL")

# --- Messaggi -------------------------------------------------------------
system = {
    "role": "system",
    "content": "Sei un assistente utile. Rispondi in italiano in modo chiaro e conciso.",
}

# --- Ciclo domande --------------------------------------------------------
print('Scrivere una domanda ("esci" o Ctrl+C per uscire).')
try:
    while True:
        domanda = input("Domanda: ").strip()
        if not domanda:
            continue
        if domanda.lower() == "esci":
            break

        # Nessuna cronologia: ogni domanda parte da zero.
        messages = [system, {"role": "user", "content": domanda}]

        # --- Payload ------------------------------------------------------
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 512,
            "reasoning_effort": "none",
            "stream": False,
        }

        # --- Chiamata -----------------------------------------------------
        try:
            response = requests.post(
                f"{base_url}/chat/completions", json=payload, timeout=60
            )
            response.raise_for_status()
            print(response.json()["choices"][0]["message"]["content"])
        except requests.exceptions.Timeout:
            print("Attesa scaduta: controllare server, carico e tempi.")
        except requests.exceptions.ConnectionError:
            print("Connessione fallita: controllare server, URL e porta.")
        except requests.exceptions.HTTPError:
            print("Errore HTTP:", response.status_code, response.text)
except (KeyboardInterrupt, EOFError):
    print()

print("Arrivederci.")
