"""Strumento convertitore: conversioni fra unità di misura di un elenco chiuso."""
import math

from langchain_core.tools import BaseTool, StructuredTool

# Grandezze lineari: fattore che porta l'unità nell'unità base (m, kg, l).
_FATTORI: dict[str, dict[str, float]] = {
    "lunghezza": {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
                  "in": 0.0254, "ft": 0.3048, "mi": 1609.344},
    "massa": {"mg": 1e-6, "g": 0.001, "kg": 1.0, "t": 1000.0,
              "oz": 0.028349523125, "lb": 0.45359237},
    "volume": {"ml": 0.001, "l": 1.0},
}
# Temperatura: conversione non lineare, passando per il kelvin.
_IN_KELVIN = {"C": lambda v: v + 273.15, "F": lambda v: (v - 32) * 5 / 9 + 273.15, "K": lambda v: v}
_DA_KELVIN = {"C": lambda k: k - 273.15, "F": lambda k: (k - 273.15) * 9 / 5 + 32, "K": lambda k: k}

UNITA: dict[str, tuple[str, ...]] = {
    **{grandezza: tuple(fattori) for grandezza, fattori in _FATTORI.items()},
    "temperatura": tuple(_IN_KELVIN),
}
_GRANDEZZA = {unita: grandezza for grandezza, elenco in UNITA.items() for unita in elenco}
_ELENCO = "; ".join(f"{g}: {', '.join(u)}" for g, u in UNITA.items())
_TOLLERANZA_K = 1e-9  # arrotondamenti: -459.67 F deve dare 0 K, non un errore


def _numero(x: float) -> str:
    return f"{x + 0.0:.10g}"  # + 0.0 trasforma -0.0 in 0.0


def converti(valore: float, da: str, a: str) -> str:
    """Converte `valore` da `da` ad `a`, oppure restituisce un messaggio di errore leggibile."""
    for unita in (da, a):
        if unita not in _GRANDEZZA:
            return f"Errore: unità non supportata: '{unita}'. Unità ammesse: {_ELENCO}."
    if _GRANDEZZA[da] != _GRANDEZZA[a]:
        return (f"Errore: conversione incompatibile da '{da}' ({_GRANDEZZA[da]}) "
                f"a '{a}' ({_GRANDEZZA[a]}).")
    if not math.isfinite(valore):
        return f"Errore: il valore deve essere un numero finito (ricevuto: {valore})."
    if _GRANDEZZA[da] == "temperatura":
        kelvin = _IN_KELVIN[da](valore)
        if kelvin < -_TOLLERANZA_K:
            return f"Errore: temperatura sotto lo zero assoluto: {_numero(valore)} {da}."
        risultato = _DA_KELVIN[a](max(kelvin, 0.0))
    else:
        fattori = _FATTORI[_GRANDEZZA[da]]
        risultato = valore * fattori[da] / fattori[a]
    if not math.isfinite(risultato):
        return "Errore: risultato fuori dall'intervallo rappresentabile."
    return f"{_numero(valore)} {da} = {_numero(risultato)} {a}"


def crea_strumento_convertitore() -> BaseTool:
    """Costruisce lo strumento `convertitore_unita`."""

    def convertitore_unita(valore: float, da: str, a: str) -> str:
        return converti(valore, da, a)

    return StructuredTool.from_function(
        func=convertitore_unita,
        name="convertitore_unita",
        description=("Converte un valore fra due unità di misura della stessa grandezza. "
                     f"Usa esattamente questi simboli: {_ELENCO}."),
    )
