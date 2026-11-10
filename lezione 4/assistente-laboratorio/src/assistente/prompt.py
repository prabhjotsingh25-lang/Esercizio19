"""Prompt dell'utente: modelli di richiesta scelti con /prompt (prompt MCP nella variante mcp).

Una sola definizione (catalogo); i canali cambiano: nella variante mcp elenco e testo arrivano
dal server con prompts/list e prompts/get, nelle altre dal catalogo locale. L'host controlla
nome e argomenti rispetto all'elenco prima di chiedere il testo; nessun controllo di formato.
"""
import logging
import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from assistente.contesto import NOME_PROMPT

log = logging.getLogger("assistente.prompt")

__all__ = ["CATALOGO_PROMPT", "NOME_PROMPT", "ArgomentoPrompt", "DefinizionePrompt", "ErrorePrompt",
           "FontePrompt", "FontePromptLocale", "InfoPrompt", "analizza_comando", "controlla",
           "descrivi_elenco", "log_messaggi"]


class ErrorePrompt(ValueError):
    """Comando /prompt non valido o prompt non disponibile: il messaggio è per l'utente."""


@dataclass(frozen=True)
class ArgomentoPrompt:
    nome: str
    descrizione: str
    obbligatorio: bool
    predefinito: str | None = None  # usato dal catalogo quando l'argomento facoltativo manca


@dataclass(frozen=True)
class InfoPrompt:
    """Voce dell'elenco (prompts/list): ciò che l'host usa per controllare il comando."""
    nome: str
    descrizione: str
    argomenti: tuple[ArgomentoPrompt, ...]


@dataclass(frozen=True)
class DefinizionePrompt(InfoPrompt):
    modello: str = ""  # testo con i segnaposto {argomento}

    def componi(self, argomenti: dict[str, str]) -> str:
        valori = {a.nome: argomenti.get(a.nome) or a.predefinito or "" for a in self.argomenti}
        return self.modello.format(**valori)


CATALOGO_PROMPT: tuple[DefinizionePrompt, ...] = (
    DefinizionePrompt(
        nome="spiega",
        descrizione="Spiega un concetto con una spiegazione adatta al livello indicato.",
        argomenti=(ArgomentoPrompt("argomento", "Il concetto da spiegare.", True),
                   ArgomentoPrompt("livello", "Livello della spiegazione (per esempio base, "
                                   "intermedio, avanzato); predefinito: base.", False, "base")),
        modello=("Spiegami {argomento} con una spiegazione di livello {livello}: adatta lessico, "
                 "lunghezza e dettagli a quel livello.")),
    DefinizionePrompt(
        nome="riassumi_conversazione",
        descrizione="Riassume i turni della sessione corrente nello stile indicato.",
        argomenti=(ArgomentoPrompt("stile", "Stile del riassunto (per esempio sintetico, a punti, "
                                   "dettagliato).", True),),
        modello=("Riassumi i turni della sessione corrente nello stile {stile}. Usa solo quello "
                 "che ci siamo detti in questa conversazione.")),
)


class FontePrompt(Protocol):
    """Da dove arrivano i prompt: catalogo locale o server MCP."""

    def elenca(self) -> list[InfoPrompt]: ...

    def ottieni(self, nome: str, argomenti: dict[str, str]) -> list[BaseMessage]: ...


def analizza_comando(resto: str) -> tuple[str, dict[str, str]]:
    """`nome arg=valore arg2="valore con spazi"` → (nome, argomenti)."""
    try:
        parti = shlex.split(resto)
    except ValueError:
        raise ErrorePrompt("virgolette non chiuse nel comando") from None
    if not parti:
        raise ErrorePrompt("manca il nome del prompt: /prompt nome argomento=valore")
    nome, argomenti = parti[0], {}
    for parte in parti[1:]:
        chiave, uguale, valore = parte.partition("=")
        if not uguale or not chiave:
            raise ErrorePrompt(f"argomento non valido: {parte!r} (usa nome=valore)")
        if chiave in argomenti:
            raise ErrorePrompt(f"argomento ripetuto: {chiave}")
        argomenti[chiave] = valore
    return nome, argomenti


def controlla(elenco: Sequence[InfoPrompt], nome: str, argomenti: dict[str, str]) -> InfoPrompt:
    """Controlla nome e argomenti rispetto a prompts/list; ErrorePrompt se qualcosa non va."""
    info = next((i for i in elenco if i.nome == nome), None)
    if info is None:
        disponibili = ", ".join(i.nome for i in elenco) or "nessuno"
        raise ErrorePrompt(f"prompt sconosciuto: {nome} (disponibili: {disponibili})")
    noti = {a.nome for a in info.argomenti}
    sconosciuti = [k for k in argomenti if k not in noti]
    if sconosciuti:
        raise ErrorePrompt(f"argomento sconosciuto: {', '.join(sconosciuti)} "
                           f"(argomenti di {nome}: {', '.join(sorted(noti))})")
    mancanti = [a.nome for a in info.argomenti if a.obbligatorio and not argomenti.get(a.nome)]
    if mancanti:
        raise ErrorePrompt(f"argomento obbligatorio mancante: {', '.join(mancanti)}")
    return info


def descrivi_elenco(elenco: Sequence[InfoPrompt]) -> str:
    """Testo di /prompts: nome, descrizione e argomenti di ogni prompt."""
    if not elenco:
        return "Nessun prompt disponibile."
    righe = []
    for info in elenco:
        righe.append(f"{info.nome} — {info.descrizione}")
        for a in info.argomenti:
            tipo = "obbligatorio" if a.obbligatorio else "facoltativo"
            righe.append(f"    {a.nome} ({tipo}): {a.descrizione}")
    return "\n".join(righe)


def log_messaggi(origine: str, nome: str, argomenti: dict, messaggi: Sequence[BaseMessage]) -> None:
    ruoli = " | ".join(f"[{'user' if isinstance(m, HumanMessage) else 'assistant'}] {m.content}"
                       for m in messaggi)
    log.info("prompt: prompts/get %s (%s) argomenti=%s -> messaggi dal server: %s",
             nome, origine, argomenti, ruoli)


def messaggio(ruolo: str, testo: str) -> BaseMessage:
    """Messaggio del prompt per la cronologia: quelli dell'utente sono marcati name="prompt"."""
    return HumanMessage(testo, name=NOME_PROMPT) if ruolo == "user" else AIMessage(testo)


class FontePromptLocale:
    """Catalogo locale (varianti locale e http)."""

    def elenca(self) -> list[InfoPrompt]:
        log.info("prompt: prompts/list (locale) -> %d prompt: %s", len(CATALOGO_PROMPT),
                 ", ".join(d.nome for d in CATALOGO_PROMPT))
        return list(CATALOGO_PROMPT)

    def ottieni(self, nome: str, argomenti: dict[str, str]) -> list[BaseMessage]:
        definizione = next((d for d in CATALOGO_PROMPT if d.nome == nome), None)
        if definizione is None:
            raise ErrorePrompt(f"prompt sconosciuto: {nome}")
        messaggi = [messaggio("user", definizione.componi(argomenti))]
        log_messaggi("locale", nome, argomenti, messaggi)
        return messaggi
