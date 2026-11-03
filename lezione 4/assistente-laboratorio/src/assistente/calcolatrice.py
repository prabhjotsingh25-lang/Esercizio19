"""Strumento calcolatrice: espressioni aritmetiche valutate senza eval, su una whitelist dell'AST."""
import ast
import math
import operator

from langchain_core.tools import BaseTool, StructuredTool

MAX_LUNGHEZZA = 200
MAX_ESPONENTE = 1000
AMMESSI = "numeri (decimali con il punto), + - * / % **, segno, parentesi"

_BINARI = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARI = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_SIMBOLI = {ast.FloorDiv: "divisione intera (//)", ast.BitAnd: "operatore '&'",
            ast.BitOr: "operatore '|'", ast.LShift: "operatore '<<'", ast.RShift: "operatore '>>'",
            ast.MatMult: "operatore '@'", ast.Not: "operatore logico 'not'",
            ast.Invert: "operatore '~'"}


class _Rifiuto(Exception):
    """Espressione rifiutata: il messaggio è già pronto per il modello."""


def _non_consentito(descrizione: str) -> _Rifiuto:
    return _Rifiuto(f"elemento non consentito: {descrizione}. Ammessi: {AMMESSI}.")


def _controlla(albero: ast.Expression) -> None:
    """Rifiuta, prima di calcolare qualsiasi cosa, ogni nodo fuori dalla whitelist."""
    for nodo in ast.walk(albero):
        if isinstance(nodo, (ast.Expression, ast.operator, ast.unaryop)):
            continue  # gli operatori sono controllati tramite il nodo che li contiene
        if isinstance(nodo, (ast.BinOp, ast.UnaryOp)):
            tipo = type(nodo.op)
            if tipo is ast.BitXor:
                raise _Rifiuto("'^' non indica la potenza: usa **, per esempio 2 ** 3.")
            if tipo not in _BINARI and tipo not in _UNARI:
                raise _non_consentito(_SIMBOLI.get(tipo, f"operatore {tipo.__name__}"))
        elif isinstance(nodo, ast.Constant):
            if type(nodo.value) not in (int, float):
                raise _non_consentito(f"valore non numerico {nodo.value!r}")
        elif isinstance(nodo, ast.Tuple):
            raise _Rifiuto("la virgola non è ammessa: per i decimali usa il punto, per esempio 1.5.")
        elif isinstance(nodo, ast.Name):
            raise _non_consentito(f"nome '{nodo.id}'")
        elif isinstance(nodo, ast.Call):
            raise _non_consentito("chiamata di funzione")
        elif isinstance(nodo, ast.Compare):
            raise _non_consentito("confronto")
        elif isinstance(nodo, ast.BoolOp):
            raise _non_consentito("operatore logico")
        else:
            raise _non_consentito(f"costrutto {type(nodo).__name__}")


def _valuta(nodo: ast.AST) -> float:
    """Valuta un albero già controllato da `_controlla`."""
    if isinstance(nodo, ast.Constant):
        return float(nodo.value)
    if isinstance(nodo, ast.UnaryOp):
        return _UNARI[type(nodo.op)](_valuta(nodo.operand))
    sinistra, destra = _valuta(nodo.left), _valuta(nodo.right)
    if isinstance(nodo.op, (ast.Div, ast.Mod)) and destra == 0:
        raise _Rifiuto("divisione per zero.")
    if isinstance(nodo.op, ast.Pow) and abs(destra) > MAX_ESPONENTE:
        raise _Rifiuto(f"esponente troppo grande: il massimo in valore assoluto è {MAX_ESPONENTE}.")
    try:
        risultato = _BINARI[type(nodo.op)](sinistra, destra)
    except ZeroDivisionError:  # per esempio 0 ** -1
        raise _Rifiuto("divisione per zero.") from None
    if isinstance(risultato, complex):
        raise _Rifiuto("il risultato non è un numero reale.")
    return risultato


def calcola(espressione: str) -> str:
    """Calcola l'espressione, oppure restituisce un messaggio di errore leggibile dal modello."""
    testo = espressione.strip()
    if not testo:
        return "Errore: espressione vuota."
    if len(testo) > MAX_LUNGHEZZA:
        return f"Errore: espressione troppo lunga (massimo {MAX_LUNGHEZZA} caratteri)."
    try:
        albero = ast.parse(testo, mode="eval")  # solo analisi del testo: nulla viene eseguito
    except (SyntaxError, ValueError) as errore:
        motivo = getattr(errore, "msg", None) or str(errore)
        return f"Errore: espressione non valida ({motivo}). Ammessi: {AMMESSI}."
    try:
        _controlla(albero)
        risultato = _valuta(albero.body)
    except _Rifiuto as rifiuto:
        return f"Errore: {rifiuto}"
    except OverflowError:
        risultato = math.inf
    if not math.isfinite(risultato):
        return "Errore: risultato fuori dall'intervallo rappresentabile."
    return f"{testo} = {risultato + 0.0:.12g}"  # + 0.0 trasforma -0.0 in 0.0


def crea_strumento_calcolatrice() -> BaseTool:
    """Costruisce lo strumento `calcolatrice_sicura`."""

    def calcolatrice_sicura(espressione: str) -> str:
        return calcola(espressione)

    return StructuredTool.from_function(
        func=calcolatrice_sicura,
        name="calcolatrice_sicura",
        description=("Calcola un'espressione aritmetica e restituisce il risultato. "
                     f"Ammessi solo: {AMMESSI}; la potenza si scrive **. "
                     "Niente variabili né funzioni. Esempio: (17 + 4) * 3"),
    )
