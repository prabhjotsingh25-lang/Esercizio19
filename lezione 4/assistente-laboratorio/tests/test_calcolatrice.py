import pytest
from finti import ModelloFinto
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.calcolatrice import calcola, crea_strumento_calcolatrice
from assistente.grafo import costruisci_grafo


@pytest.mark.parametrize("espressione, atteso", [
    ("2 + 3 * 4", "2 + 3 * 4 = 14"),
    ("(2 + 3) * 4", "(2 + 3) * 4 = 20"),
    ("10 / 4", "10 / 4 = 2.5"),
    ("7 % 3", "7 % 3 = 1"),
    ("2 ** 10", "2 ** 10 = 1024"),
    ("2 ** 0.5", "2 ** 0.5 = 1.41421356237"),
    ("-3 + +5", "-3 + +5 = 2"),
    ("-(2 - 5)", "-(2 - 5) = 3"),
    ("0.1 + 0.2", "0.1 + 0.2 = 0.3"),
    ("1 / 3 * 3", "1 / 3 * 3 = 1"),
    ("2 ** -1", "2 ** -1 = 0.5"),
    ("  42  ", "42 = 42"),
    ("1.5e3 + 1", "1.5e3 + 1 = 1501"),
])
def test_espressioni_valide(espressione, atteso):
    assert calcola(espressione) == atteso


@pytest.mark.parametrize("espressione", ["", "   "])
def test_espressione_vuota(espressione):
    assert calcola(espressione) == "Errore: espressione vuota."


def test_espressione_troppo_lunga():
    assert calcola("1+" * 100 + "1").startswith("Errore: espressione troppo lunga")


@pytest.mark.parametrize("espressione", ["2 +", "(1 + 2", "3 4", "1 + * 2", "x = 1"])
def test_sintassi_non_valida(espressione):
    assert calcola(espressione).startswith("Errore: espressione non valida")


@pytest.mark.parametrize("espressione", ["1,5 + 2", "(1,5) * 2"])
def test_virgola_decimale(espressione):
    risultato = calcola(espressione)
    assert risultato.startswith("Errore:") and "punto" in risultato


def test_accento_circonflesso_non_e_potenza():
    risultato = calcola("2 ^ 3")
    assert risultato.startswith("Errore:") and "**" in risultato


@pytest.mark.parametrize("espressione, descrizione", [
    ("x + 1", "nome 'x'"),
    ("pi * 2", "nome 'pi'"),
    ("sqrt(2)", "chiamata di funzione"),
    ("7 // 2", "divisione intera"),
    ("1 < 2", "confronto"),
    ("1 and 2", "operatore logico"),
    ("'a' * 3", "valore non numerico"),
    ("True + 1", "valore non numerico"),
    ("2j * 2", "valore non numerico"),
    ("1 & 3", "operatore"),
])
def test_elementi_non_consentiti(espressione, descrizione):
    risultato = calcola(espressione)
    assert risultato.startswith(f"Errore: elemento non consentito: {descrizione}")
    assert "+ - * / % **" in risultato


@pytest.mark.parametrize("espressione", [
    "__import__('os').system('echo pericolo')",
    "().__class__.__bases__[0].__subclasses__()",
    "open('segreti.txt').read()",
    "(lambda: 1)()",
    "[1, 2][0]",
    "{'a': 1}",
    "print(1)",
    "eval('1+1')",
])
def test_tentativi_di_iniezione_rifiutati(espressione):
    assert calcola(espressione).startswith("Errore:")


def test_nessuna_esecuzione_durante_il_rifiuto(monkeypatch):
    chiamate = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: chiamate.append(a))
    calcola("print('eseguito')")
    assert chiamate == []


@pytest.mark.parametrize("espressione", ["1 / 0", "5 % 0", "1 / (2 - 2)", "0 ** -1"])
def test_divisione_per_zero(espressione):
    assert calcola(espressione) == "Errore: divisione per zero."


@pytest.mark.parametrize("espressione", ["9 ** 9 ** 9", "2 ** 1001", "2 ** -5000"])
def test_esponente_troppo_grande(espressione):
    assert calcola(espressione).startswith("Errore: esponente troppo grande")


@pytest.mark.parametrize("espressione", ["10.0 ** 400", "1e308 * 10", "1e400"])
def test_risultato_fuori_intervallo(espressione):
    assert calcola(espressione) == "Errore: risultato fuori dall'intervallo rappresentabile."


def test_risultato_non_reale():
    assert calcola("(-8) ** 0.5") == "Errore: il risultato non è un numero reale."


def test_strumento_langchain():
    strumento = crea_strumento_calcolatrice()
    assert strumento.name == "calcolatrice_sicura"
    assert strumento.args_schema.model_json_schema()["required"] == ["espressione"]
    assert "**" in strumento.description
    assert strumento.invoke({"espressione": "(17 + 4) * 3"}) == "(17 + 4) * 3 = 63"


def test_ciclo_completo_nel_grafo():
    richiesta = AIMessage("", tool_calls=[
        {"name": "calcolatrice_sicura", "args": {"espressione": "1 / 0"}, "id": "k1"}])
    m = ModelloFinto(risposte=[richiesta, AIMessage("Non si può dividere per zero.")])
    out = costruisci_grafo(m, [crea_strumento_calcolatrice()], 3).invoke(
        {"messages": [HumanMessage("Quanto fa 1 diviso 0?")], "passaggi": 0})
    risultati = [t.content for t in out["messages"] if isinstance(t, ToolMessage)]
    assert risultati == ["Errore: divisione per zero."]
    assert out["messages"][-1].content == "Non si può dividere per zero."
