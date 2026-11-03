"""Strumento giorni e scadenze: conteggi fra date ISO e scadenze, con festività da file locale.

Il risultato è indicativo e non normativo: festività nazionali italiane, escluse le patronali.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool

PERCORSO_FESTIVITA = Path(__file__).parent / "dati" / "festivita.json"
MAX_GIORNI = 3650
NOTA = "(Calcolo indicativo, non normativo.)"
NOTA_LAVORATIVI = ("(Calcolo indicativo, non normativo: festività nazionali italiane "
                   "da file locale, escluse le patronali.)")
_GIORNI_SETTIMANA = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
_FORMATO_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


class _Rifiuto(Exception):
    """Richiesta rifiutata: il messaggio è già pronto per il modello."""


class _Festivita:
    """Festività lette dal file: date fisse ogni anno più Pasquetta per gli anni coperti."""

    def __init__(self, percorso: Path):
        try:
            dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
            self._fisse = [tuple(int(x) for x in giorno.split("-")) for giorno in dati["fisse"]]
            self._pasquetta = {int(a): date.fromisoformat(g) for a, g in dati["pasquetta"].items()}
            for mese, giorno in self._fisse:
                date(2000, mese, giorno)  # 2000 è bisestile: accetta anche il 29 febbraio
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise _Rifiuto("file delle festività non disponibile o non valido.") from None
        if not self._pasquetta:
            raise _Rifiuto("file delle festività non disponibile o non valido.")
        self.anni = (min(self._pasquetta), max(self._pasquetta))

    def controlla_anno(self, anno: int) -> None:
        if anno not in self._pasquetta:
            raise _Rifiuto(f"festività non disponibili per il {anno}: il calcolo dei giorni "
                           f"lavorativi copre gli anni {self.anni[0]}-{self.anni[1]}.")

    def e_festivo(self, giorno: date) -> bool:
        self.controlla_anno(giorno.year)
        return (giorno.month, giorno.day) in self._fisse or giorno == self._pasquetta[giorno.year]


def _data(valore: str, nome: str) -> date:
    try:
        if _FORMATO_ISO.fullmatch(valore):
            return date.fromisoformat(valore)
    except ValueError:
        pass
    raise _Rifiuto(f"{nome} non valida: '{valore}'. Usa il formato AAAA-MM-GG, "
                   "per esempio 2026-11-03.")


def _plurale(n: int, singolare: str, plurale: str) -> str:
    return f"{n} {singolare if abs(n) == 1 else plurale}"


def _elenco(giorni: list[date]) -> str:
    return ", ".join(str(g) for g in giorni) or "nessuna"


def _conta(inizio: date, fine: date, festivita: _Festivita | None) -> str:
    distanza = (fine - inizio).days
    if abs(distanza) > MAX_GIORNI:
        raise _Rifiuto(f"le date distano più di {MAX_GIORNI} giorni.")
    if festivita is None:
        return (f"Dal {inizio} al {fine}: "
                f"{_plurale(distanza, 'giorno', 'giorni')} di calendario. {NOTA}")
    primo, ultimo = sorted((inizio, fine))
    for anno in range(primo.year, ultimo.year + 1):
        festivita.controlla_anno(anno)
    lavorativi, escluse = 0, []
    for scarto in range(1, abs(distanza) + 1):  # giorni in (primo, ultimo]
        giorno = primo + timedelta(days=scarto)
        if giorno.weekday() >= 5:
            continue
        if festivita.e_festivo(giorno):
            escluse.append(giorno)
        else:
            lavorativi += 1
    segno = -1 if distanza < 0 else 1
    return (f"Dal {inizio} al {fine}: "
            f"{_plurale(segno * lavorativi, 'giorno lavorativo', 'giorni lavorativi')}; "
            f"festività escluse: {_elenco(escluse)}. {NOTA_LAVORATIVI}")


def _scadenza(inizio: date, giorni: int, festivita: _Festivita | None) -> str:
    if abs(giorni) > MAX_GIORNI:
        raise _Rifiuto(f"giorni deve essere compreso fra -{MAX_GIORNI} e {MAX_GIORNI}.")
    operazione = f"{inizio} {'-' if giorni < 0 else '+'} "
    if festivita is None:
        arrivo = inizio + timedelta(days=giorni)
        return (f"{operazione}{_plurale(abs(giorni), 'giorno', 'giorni')} = {arrivo} "
                f"({_GIORNI_SETTIMANA[arrivo.weekday()]}). {NOTA}")
    passo = timedelta(days=-1 if giorni < 0 else 1)
    arrivo, contati, saltate = inizio, 0, []
    while contati < abs(giorni):
        arrivo += passo
        if arrivo.weekday() >= 5:
            continue
        if festivita.e_festivo(arrivo):
            saltate.append(arrivo)
        else:
            contati += 1
    return (f"{operazione}{_plurale(abs(giorni), 'giorno lavorativo', 'giorni lavorativi')} = "
            f"{arrivo} ({_GIORNI_SETTIMANA[arrivo.weekday()]}); "
            f"festività saltate: {_elenco(saltate)}. {NOTA_LAVORATIVI}")


def calcola_giorni(data_inizio: str, data_fine: str | None = None, giorni: int | None = None,
                   solo_lavorativi: bool = False, percorso: Path = PERCORSO_FESTIVITA) -> str:
    """Conta i giorni fino a `data_fine` oppure calcola la scadenza dopo `giorni`.

    Restituisce il risultato oppure un messaggio di errore leggibile dal modello.
    """
    if data_fine is not None and not data_fine.strip():
        data_fine = None  # una stringa vuota vale come argomento assente
    try:
        inizio = _data(data_inizio, "data_inizio")
        if (data_fine is None) == (giorni is None):
            raise _Rifiuto("indica esattamente uno tra data_fine (per contare i giorni fra due "
                           "date) e giorni (per calcolare una scadenza).")
        festivita = _Festivita(percorso) if solo_lavorativi else None
        if data_fine is not None:
            return _conta(inizio, _data(data_fine, "data_fine"), festivita)
        return _scadenza(inizio, giorni, festivita)
    except _Rifiuto as rifiuto:
        return f"Errore: {rifiuto}"


def crea_strumento_scadenze(percorso: Path = PERCORSO_FESTIVITA) -> BaseTool:
    """Costruisce lo strumento `giorni_scadenze`; `percorso` è iniettabile per i test."""

    def giorni_scadenze(data_inizio: str, data_fine: str | None = None, giorni: int | None = None,
                        solo_lavorativi: bool = False) -> str:
        return calcola_giorni(data_inizio, data_fine, giorni, solo_lavorativi, percorso)

    return StructuredTool.from_function(
        func=giorni_scadenze,
        name="giorni_scadenze",
        description=("Conta i giorni fra due date oppure calcola una data di scadenza. "
                     "Date nel formato AAAA-MM-GG. Passa data_fine per contare i giorni da "
                     "data_inizio a data_fine, oppure giorni (anche negativo) per calcolare la "
                     "scadenza: uno solo dei due. Con solo_lavorativi=true esclude sabati, "
                     "domeniche e festività nazionali italiane (anni 2025-2030). "
                     "Se serve la data di oggi, ottienila prima con lo strumento di data e ora. "
                     "Il risultato è indicativo, non normativo."),
    )
