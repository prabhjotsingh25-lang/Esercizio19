// Chat dell'assistente: parla solo con il back-end (window.CONFIG.backendUrl, da /config.js).
// Ogni chiamata passa da api(METODO, `percorso`): un test confronta percorsi e metodi con
// docs/openapi-backend.json.
"use strict";

const CONFIG = window.CONFIG;
const stato = { attuale: null, occupato: false };
const $ = (id) => document.getElementById(id);

class ErroreBackend extends Error {
  constructor(messaggio, codice) {
    super(messaggio);
    this.codice = codice;
  }
}

async function api(metodo, percorso, corpo) {
  let risposta;
  try {
    risposta = await fetch(CONFIG.backendUrl + percorso, {
      method: metodo,
      headers: corpo === undefined ? {} : { "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
      signal: AbortSignal.timeout(CONFIG.timeoutMs),
    });
  } catch (e) {
    if (e.name === "TimeoutError") {
      throw new ErroreBackend("Il back-end non ha risposto in tempo: riprova più tardi.", 0);
    }
    throw new ErroreBackend(
      `Non riesco a raggiungere il back-end su ${CONFIG.backendUrl}: controlla che sia avviato.`, 0);
  }
  if (risposta.status === 204) return null;
  let dati = null;
  try { dati = await risposta.json(); } catch { /* corpo non JSON */ }
  if (!risposta.ok) {
    const dettaglio = dati && typeof dati.detail === "string" ? dati.detail : risposta.statusText;
    throw new ErroreBackend(messaggioErrore(risposta.status, dettaglio), risposta.status);
  }
  return dati;
}

function messaggioErrore(codice, dettaglio) {
  if (codice === 409) return "C'è già una risposta in arrivo per questa chat: aspetta che finisca.";
  if (codice === 404) return "Questa chat non esiste più.";
  if (codice === 504) return `L'assistente non ha risposto in tempo (${dettaglio}). Puoi riprovare.`;
  if (codice === 503 || codice === 502) return `Servizio non disponibile: ${dettaglio}. Puoi riprovare.`;
  return `Errore ${codice}: ${dettaglio}`;
}

function mostraAvviso(testo) {
  const avviso = $("avviso");
  avviso.textContent = testo || "";
  avviso.hidden = !testo;
}

function data(iso) {
  return new Date(iso).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

function elemento(tag, classe, testo) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (testo !== undefined) e.textContent = testo;
  return e;
}

// --- elenco delle chat ---

async function caricaElenco() {
  let elenco;
  try {
    elenco = await api("GET", `/conversazioni`);
  } catch (e) {
    mostraAvviso(e.message);
    return;
  }
  const lista = $("chat");
  lista.replaceChildren();
  for (const c of elenco) {
    const voce = elemento("li", c.id === stato.attuale ? "attiva" : "");
    const info = elemento("div", "info");
    info.append(elemento("div", "titolo", c.titolo || "Nuova chat"),
                elemento("div", "data", data(c.ultimo_messaggio)));
    const elimina = elemento("button", "elimina", "✕");
    elimina.title = "Elimina la chat";
    elimina.addEventListener("click", (ev) => { ev.stopPropagation(); eliminaChat(c.id); });
    voce.append(info, elimina);
    voce.addEventListener("click", () => apriChat(c.id));
    lista.append(voce);
  }
}

async function nuovaChat() {
  const conv = await api("POST", `/conversazioni`);
  stato.attuale = conv.id;
  mostraMessaggi(conv.messaggi);
  await caricaElenco();
  return conv.id;
}

async function eliminaChat(id) {
  if (!confirm("Eliminare questa chat?")) return;
  try {
    await api("DELETE", `/conversazioni/${id}`);
    if (stato.attuale === id) { stato.attuale = null; mostraMessaggi([]); }
    mostraAvviso("");
  } catch (e) {
    mostraAvviso(e.message);
  }
  await caricaElenco();
}

async function apriChat(id) {
  try {
    const conv = await api("GET", `/conversazioni/${id}`);
    stato.attuale = conv.id;
    mostraMessaggi(conv.messaggi);
    if (conv.turno_in_corso) mostraAvviso("Questa chat ha una risposta in arrivo: aggiorna tra poco.");
    else mostraAvviso("");
  } catch (e) {
    mostraAvviso(e.message);
  }
  await caricaElenco();
}

// --- messaggi ---

function mostraMessaggi(messaggi) {
  const area = $("messaggi");
  area.replaceChildren();
  if (!messaggi.length) {
    area.append(elemento("p", "vuoto", "Scrivi una domanda per iniziare."));
    return;
  }
  messaggi.forEach((m, i) => area.append(bolla(m, i === messaggi.length - 1)));
  area.scrollTop = area.scrollHeight;
}

function bolla(m, ultimo) {
  const div = elemento("div", `messaggio ${m.ruolo}`, m.testo);
  if (m.ruolo === "assistente" && m.strumenti && m.strumenti.length) {
    div.append(strumentiUsati(m.strumenti));
  }
  if (m.ruolo === "utente" && m.stato === "errore") {
    div.classList.add("in-errore");
    const box = elemento("div", "errore", `Nessuna risposta: ${m.errore}.`);
    if (ultimo) {
      const bottone = elemento("button", "", "Riprova");
      bottone.type = "button";
      bottone.addEventListener("click", riprova);
      box.append(bottone);
    }
    div.append(box);
  }
  div.append(elemento("span", "ora", data(m.creato)));
  return div;
}

function strumentiUsati(strumenti) {
  const dettagli = elemento("details", "strumenti");
  dettagli.append(elemento("summary", "", `Strumenti usati (${strumenti.length})`));
  const lista = elemento("ul");
  for (const s of strumenti) {
    const voce = elemento("li");
    voce.append(elemento("strong", "", s.nome), " ",
                elemento("code", "", JSON.stringify(s.argomenti)), " → ",
                elemento("span", "", s.risultato));
    lista.append(voce);
  }
  dettagli.append(lista);
  return dettagli;
}

// --- turno: attesa con cronometro, errori, riprova ---

function inAttesa(testoDomanda) {
  const area = $("messaggi");
  area.querySelector(".vuoto")?.remove();
  if (testoDomanda) area.append(elemento("div", "messaggio utente", testoDomanda));
  const attesa = elemento("div", "messaggio attesa");
  area.append(attesa);
  area.scrollTop = area.scrollHeight;
  const inizio = Date.now();
  const aggiorna = () => {
    const s = Math.floor((Date.now() - inizio) / 1000);
    attesa.textContent = `In attesa della risposta… ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  aggiorna();
  const timer = setInterval(aggiorna, 1000);
  return () => clearInterval(timer);
}

function occupa(si) {
  stato.occupato = si;
  $("manda").disabled = si;
  $("testo").disabled = si;
  $("nuova").disabled = si;
}

async function turno(esegui, testoDomanda) {
  occupa(true);
  mostraAvviso("");
  const ferma = inAttesa(testoDomanda);
  try {
    await esegui();
  } catch (e) {
    mostraAvviso(e.message);
  } finally {
    ferma();
    // Lo storico del back-end è la fonte: la domanda in errore resta salvata con il motivo.
    // Si ricarica prima di riattivare l'invio, così non resta visibile l'attesa ferma.
    if (stato.attuale) await apriChatSilenziosa(stato.attuale);
    await caricaElenco();
    occupa(false);
  }
}

async function apriChatSilenziosa(id) {
  try {
    const conv = await api("GET", `/conversazioni/${id}`);
    mostraMessaggi(conv.messaggi);
  } catch { /* l'avviso mostra già l'errore del turno */ }
}

async function invia(ev) {
  ev.preventDefault();
  const testo = $("testo").value.trim();
  if (!testo || stato.occupato) return;
  if (!stato.attuale) {
    // La chat si crea prima di mostrare l'attesa: crearla ridisegna l'area dei messaggi.
    try { await nuovaChat(); } catch (e) { mostraAvviso(e.message); return; }
  }
  $("testo").value = "";
  await turno(() => api("POST", `/conversazioni/${stato.attuale}/messaggi`, { testo }), testo);
}

async function riprova() {
  if (stato.occupato || !stato.attuale) return;
  await turno(() => api("POST", `/conversazioni/${stato.attuale}/riprova`));
}

$("invio").addEventListener("submit", invia);
$("testo").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); $("invio").requestSubmit(); }
});
$("nuova").addEventListener("click", async () => {
  try { await nuovaChat(); mostraAvviso(""); } catch (e) { mostraAvviso(e.message); }
});
caricaElenco();
