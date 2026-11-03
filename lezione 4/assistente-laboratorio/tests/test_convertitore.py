import pytest
from finti import ModelloFinto
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.convertitore import converti, crea_strumento_convertitore
from assistente.grafo import costruisci_grafo


@pytest.mark.parametrize("valore, da, a, atteso", [
    (1.5, "km", "m", "1.5 km = 1500 m"),
    (1, "in", "cm", "1 in = 2.54 cm"),
    (1, "mi", "km", "1 mi = 1.609344 km"),
    (2, "lb", "g", "2 lb = 907.18474 g"),
    (1, "t", "kg", "1 t = 1000 kg"),
    (250, "ml", "l", "250 ml = 0.25 l"),
    (100, "C", "F", "100 C = 212 F"),
    (32, "F", "C", "32 F = 0 C"),
    (0, "K", "C", "0 K = -273.15 C"),
    (-40, "C", "F", "-40 C = -40 F"),
    (7, "m", "m", "7 m = 7 m"),
    (-3, "m", "cm", "-3 m = -300 cm"),
])
def test_conversioni_valide(valore, da, a, atteso):
    assert converti(valore, da, a) == atteso


def test_zero_assoluto_in_fahrenheit_e_ammesso():
    assert converti(-459.67, "F", "K") == "-459.67 F = 0 K"


@pytest.mark.parametrize("da, a, sbagliata", [("xx", "m", "xx"), ("m", "KM", "KM"), ("", "m", "")])
def test_unita_non_supportata(da, a, sbagliata):
    risultato = converti(1, da, a)
    assert risultato.startswith(f"Errore: unità non supportata: '{sbagliata}'.")
    assert "lunghezza: mm, cm, m, km, in, ft, mi" in risultato and "temperatura: C, F, K" in risultato


@pytest.mark.parametrize("da, a, atteso", [
    ("kg", "m", "Errore: conversione incompatibile da 'kg' (massa) a 'm' (lunghezza)."),
    ("C", "l", "Errore: conversione incompatibile da 'C' (temperatura) a 'l' (volume)."),
])
def test_conversione_incompatibile(da, a, atteso):
    assert converti(1, da, a) == atteso


@pytest.mark.parametrize("valore", [float("nan"), float("inf"), float("-inf")])
def test_valore_non_finito(valore):
    assert converti(valore, "m", "km").startswith("Errore: il valore deve essere un numero finito")


@pytest.mark.parametrize("valore, unita", [(-1, "K"), (-274, "C"), (-460, "F")])
def test_sotto_lo_zero_assoluto(valore, unita):
    assert converti(valore, unita, "C").startswith("Errore: temperatura sotto lo zero assoluto")


def test_risultato_troppo_grande():
    assert converti(1e308, "km", "mm").startswith("Errore: risultato fuori dall'intervallo")


def test_strumento_langchain():
    strumento = crea_strumento_convertitore()
    assert strumento.name == "convertitore_unita"
    schema = strumento.args_schema.model_json_schema()
    assert sorted(schema["required"]) == ["a", "da", "valore"]
    assert "km" in strumento.description and "temperatura" in strumento.description
    assert strumento.invoke({"valore": 1.5, "da": "km", "a": "m"}) == "1.5 km = 1500 m"


def test_ciclo_completo_nel_grafo():
    richiesta = AIMessage("", tool_calls=[
        {"name": "convertitore_unita", "args": {"valore": 5, "da": "km", "a": "mi"}, "id": "c1"}])
    m = ModelloFinto(risposte=[richiesta, AIMessage("Sono circa 3,1 miglia.")])
    out = costruisci_grafo(m, [crea_strumento_convertitore()], 3).invoke(
        {"messages": [HumanMessage("5 km in miglia?")], "passaggi": 0})
    risultato = [t for t in out["messages"] if isinstance(t, ToolMessage)]
    assert [t.content for t in risultato] == ["5 km = 3.106855961 mi"]
    assert out["messages"][-1].content == "Sono circa 3,1 miglia."
