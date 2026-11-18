"""Controllo delle citazioni (lezione 8): ogni id citato tra parentesi quadre nella risposta deve
essere tra quelli dei passaggi ricevuti dagli strumenti nello stesso turno.

Il controllo osserva e registra: non modifica né blocca la risposta.
"""
import json
import re
from dataclasses import dataclass

_PARENTESI = re.compile(r"\[([^\[\]]*)\](?!\()")  # [..] ma non un link Markdown [testo](url)
_ID = re.compile(r"^\d+(?:\.\d+)*$")


@dataclass(frozen=True)
class ControlloCitazioni:
    verificate: list[str]
    sconosciute: list[str]
    ricerche: int  # risultati di strumenti con la lista `passaggi`
    passaggi_ricevuti: int  # id distinti ricevuti nel turno


def _unici(valori):
    return list(dict.fromkeys(valori))


def citazioni(testo: str) -> list[str]:
    """Token numerici tra parentesi quadre (anche più d'uno, separati da virgola o punto e virgola)."""
    trovati = []
    for contenuto in _PARENTESI.findall(testo):
        token = [t.strip() for t in re.split(r"[,;]", contenuto)]
        if token and all(_ID.match(t) for t in token):
            trovati.extend(token)
    return _unici(trovati)


def id_ricevuti(risultati: list[str]) -> tuple[list[str], int]:
    """Id dei passaggi nei risultati JSON con `passaggi`; gli altri risultati sono ignorati."""
    ids, ricerche = [], 0
    for testo in risultati:
        try:
            dati = json.loads(testo)
        except (TypeError, ValueError):
            continue
        passaggi = dati.get("passaggi") if isinstance(dati, dict) else None
        if not isinstance(passaggi, list):
            continue
        ricerche += 1
        ids.extend(str(p["id"]) for p in passaggi if isinstance(p, dict) and "id" in p)
    return _unici(ids), ricerche


def controlla(risposta: str, risultati: list[str]) -> ControlloCitazioni:
    ricevuti, ricerche = id_ricevuti(risultati)
    citati = citazioni(risposta)
    return ControlloCitazioni(verificate=[c for c in citati if c in ricevuti],
                              sconosciute=[c for c in citati if c not in ricevuti],
                              ricerche=ricerche, passaggi_ricevuti=len(ricevuti))


def riga_log(c: ControlloCitazioni) -> str:
    return (f"citazioni verificate={','.join(c.verificate) or '-'} "
            f"sconosciute={','.join(c.sconosciute) or '-'} ricerche={c.ricerche} "
            f"passaggi_ricevuti={c.passaggi_ricevuti}")
