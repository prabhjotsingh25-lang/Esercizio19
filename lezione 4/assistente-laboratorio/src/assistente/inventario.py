"""Strumento catalogo locale: ricerca e dettaglio sull'inventario del laboratorio (file CSV).

Un risultato vuoto non è un errore: lo strumento lo dice esplicitamente, con le categorie
disponibili, così il modello può riprovare o rispondere che l'articolo non c'è.
"""
import csv
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool

PERCORSO_CATALOGO = Path(__file__).parent / "dati" / "catalogo.csv"
COLONNE = ("codice", "nome", "categoria", "descrizione", "ubicazione", "quantita")
MAX_RISULTATI = 10
MAX_TESTO = 100


class _Rifiuto(Exception):
    """Richiesta rifiutata: il messaggio è già pronto per il modello."""


@dataclass(frozen=True)
class Articolo:
    codice: str
    nome: str
    categoria: str
    descrizione: str
    ubicazione: str
    quantita: int

    def riga(self) -> str:
        return (f"- {self.codice} · {self.nome} ({self.categoria}): {self.ubicazione}; "
                f"disponibili: {self.quantita}")


def _normalizza(testo: str) -> str:
    """Minuscole e senza accenti: «Umidità» e «UMIDITA» diventano uguali."""
    scomposto = unicodedata.normalize("NFKD", testo.strip())
    return "".join(c for c in scomposto if not unicodedata.combining(c)).casefold()


def _carica(percorso: Path) -> list[Articolo]:
    """Legge e valida il CSV (separatore `;`, UTF-8, anche con il BOM di Excel)."""
    try:
        with open(percorso, encoding="utf-8-sig", newline="") as file:
            lettore = csv.DictReader(file, delimiter=";")
            if tuple(lettore.fieldnames or ()) != COLONNE:
                raise ValueError("intestazione")
            articoli = []
            for riga in lettore:
                if None in riga or None in riga.values():
                    raise ValueError("numero di campi")
                valori = {nome: riga[nome].strip() for nome in COLONNE}
                quantita = int(valori.pop("quantita"))
                if quantita < 0 or not all(valori[c] for c in ("codice", "nome", "categoria")):
                    raise ValueError("valori")
                articoli.append(Articolo(**valori, quantita=quantita))
    except (OSError, ValueError, csv.Error):  # UnicodeDecodeError è un ValueError
        raise _Rifiuto("catalogo non disponibile o non valido.") from None
    codici = [a.codice.upper() for a in articoli]
    if len(set(codici)) != len(codici):
        raise _Rifiuto("catalogo non disponibile o non valido.")
    return articoli


def _categorie(articoli: list[Articolo]) -> str:
    return ", ".join(sorted({a.categoria for a in articoli}, key=_normalizza)) or "nessuna"


def _dettaglio(articoli: list[Articolo], codice: str) -> str:
    for a in articoli:
        if a.codice.upper() == codice.upper():
            return (f"Articolo {a.codice}:\n- nome: {a.nome}\n- categoria: {a.categoria}\n"
                    f"- descrizione: {a.descrizione}\n- ubicazione: {a.ubicazione}\n"
                    f"- quantità disponibile: {a.quantita}")
    return f"Nessun articolo con codice '{codice}'."


def _ricerca(articoli: list[Articolo], testo: str, categoria: str) -> str:
    if categoria and _normalizza(categoria) not in {_normalizza(a.categoria) for a in articoli}:
        raise _Rifiuto(f"categoria inesistente: '{categoria}'. "
                       f"Categorie disponibili: {_categorie(articoli)}.")
    parole = _normalizza(testo).split()
    trovati = sorted(
        (a for a in articoli
         if (not categoria or _normalizza(a.categoria) == _normalizza(categoria))
         and all(p in _normalizza(f"{a.nome} {a.descrizione} {a.categoria}") for p in parole)),
        key=lambda a: a.codice)
    criteri = " ".join(filter(None, [testo and f"per '{testo}'",
                                     categoria and f"nella categoria '{_normalizza(categoria)}'"]))
    if not trovati:
        return f"Nessun articolo trovato {criteri}. Categorie disponibili: {_categorie(articoli)}."
    intestazione = (f"Trovato 1 articolo {criteri}:" if len(trovati) == 1
                    else f"Trovati {len(trovati)} articoli {criteri}:")
    if len(trovati) > MAX_RISULTATI:
        intestazione = (f"{intestazione[:-1]}; mostrati i primi {MAX_RISULTATI}: "
                        "restringi la ricerca.")
    return "\n".join([intestazione, *(a.riga() for a in trovati[:MAX_RISULTATI])])


def cerca_nel_catalogo(testo: str = "", categoria: str = "", codice: str = "",
                       percorso: Path = PERCORSO_CATALOGO) -> str:
    """Ricerca (testo e/o categoria) oppure dettaglio (codice); errori leggibili dal modello."""
    testo, categoria, codice = (testo or "").strip(), (categoria or "").strip(), (codice or "").strip()
    try:
        if not (testo or categoria or codice):
            raise _Rifiuto("indica cosa cercare (testo e/o categoria) oppure il codice di un articolo.")
        if codice and (testo or categoria):
            raise _Rifiuto("usa codice da solo (per il dettaglio) oppure testo e/o categoria "
                           "(per la ricerca), non insieme.")
        if max(len(testo), len(categoria), len(codice)) > MAX_TESTO:
            raise _Rifiuto(f"testo troppo lungo (massimo {MAX_TESTO} caratteri).")
        articoli = _carica(percorso)
        return _dettaglio(articoli, codice) if codice else _ricerca(articoli, testo, categoria)
    except _Rifiuto as rifiuto:
        return f"Errore: {rifiuto}"


def crea_strumento_catalogo(percorso: Path = PERCORSO_CATALOGO) -> BaseTool:
    """Costruisce lo strumento `catalogo_locale`; `percorso` è iniettabile per i test."""

    def catalogo_locale(testo: str = "", categoria: str = "", codice: str = "") -> str:
        return cerca_nel_catalogo(testo, categoria, codice, percorso)

    return StructuredTool.from_function(
        func=catalogo_locale,
        name="catalogo_locale",
        description=("Cerca nell'inventario del laboratorio (strumenti, componenti, materiali) "
                     "e dice dove si trovano e quanti ce ne sono. Per cercare passa testo "
                     "(parole del nome o della descrizione) e/o categoria; per il dettaglio di "
                     "un articolo passa solo codice, per esempio MUL-01. Se non trova nulla lo "
                     "dice: in quel caso l'articolo non è in inventario."),
    )
