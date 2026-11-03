import csv

import pytest
from finti import ModelloFinto
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.grafo import costruisci_grafo
from assistente.inventario import (COLONNE, PERCORSO_CATALOGO, cerca_nel_catalogo,
                                   crea_strumento_catalogo)

INTESTAZIONE = "codice;nome;categoria;descrizione;ubicazione;quantita"
RIGHE = [
    "MUL-01;Multimetro digitale;misura;Tensione, corrente e resistenza;Armadio A, ripiano 2;6",
    "MUL-02;Multimetro analogico;misura;A lancetta, per esercitazioni;Armadio A, ripiano 2;3",
    "OSC-01;Oscilloscopio digitale;misura;Due canali, 100 MHz;Banco docente;2",
    "ALI-01;Alimentatore da banco;alimentazione;Uscita regolabile 0-30 V;Armadio B;8",
    "SEN-03;Sensore di umidità DHT22;sensori;Temperatura e umidità relativa;Cassettiera B;0",
]


def _scrivi(percorso, righe, intestazione=INTESTAZIONE, codifica="utf-8"):
    percorso.write_text("\n".join([intestazione, *righe]) + "\n", encoding=codifica)
    return percorso


@pytest.fixture
def catalogo(tmp_path):
    return _scrivi(tmp_path / "catalogo.csv", RIGHE)


def _cerca(percorso, **argomenti):
    return cerca_nel_catalogo(percorso=percorso, **argomenti)


# --- ricerca --------------------------------------------------------------------------------

def test_ricerca_per_testo(catalogo):
    assert _cerca(catalogo, testo="multimetro") == (
        "Trovati 2 articoli per 'multimetro':\n"
        "- MUL-01 · Multimetro digitale (misura): Armadio A, ripiano 2; disponibili: 6\n"
        "- MUL-02 · Multimetro analogico (misura): Armadio A, ripiano 2; disponibili: 3")


@pytest.mark.parametrize("testo", ["UMIDITA", "umidità", "  Umidita  "])
def test_ricerca_ignora_maiuscole_e_accenti(catalogo, testo):
    assert _cerca(catalogo, testo=testo).startswith("Trovato 1 articolo per")
    assert "SEN-03 · Sensore di umidità DHT22 (sensori): Cassettiera B; disponibili: 0" in _cerca(
        catalogo, testo=testo)


def test_ricerca_con_piu_parole_le_richiede_tutte(catalogo):
    risultato = _cerca(catalogo, testo="multimetro lancetta")
    assert risultato.startswith("Trovato 1 articolo per 'multimetro lancetta':") and "MUL-02" in risultato


def test_ricerca_nella_descrizione(catalogo):
    assert "OSC-01" in _cerca(catalogo, testo="100 mhz")


def test_ricerca_per_categoria(catalogo):
    risultato = _cerca(catalogo, categoria="Misura")
    assert risultato.startswith("Trovati 3 articoli nella categoria 'misura':")
    assert [r[2:8] for r in risultato.splitlines()[1:]] == ["MUL-01", "MUL-02", "OSC-01"]


def test_ricerca_per_testo_e_categoria(catalogo):
    risultato = _cerca(catalogo, testo="digitale", categoria="misura")
    assert risultato.startswith("Trovati 2 articoli per 'digitale' nella categoria 'misura':")


def test_troppi_risultati_vengono_troncati(tmp_path):
    righe = [f"K-{i:02d};Kit numero {i};componenti;Assortimento;Cassetto;1" for i in range(23, 0, -1)]
    risultato = _cerca(_scrivi(tmp_path / "c.csv", righe), testo="kit")
    linee = risultato.splitlines()
    assert linee[0] == "Trovati 23 articoli per 'kit'; mostrati i primi 10: restringi la ricerca."
    assert [l[2:6] for l in linee[1:]] == [f"K-{i:02d}" for i in range(1, 11)]


# --- risultati vuoti (non sono errori) -------------------------------------------------------

def test_nessun_risultato(catalogo):
    assert _cerca(catalogo, testo="microscopio elettronico") == (
        "Nessun articolo trovato per 'microscopio elettronico'. "
        "Categorie disponibili: alimentazione, misura, sensori.")


def test_nessun_risultato_nella_categoria(catalogo):
    assert _cerca(catalogo, testo="multimetro", categoria="sensori").startswith(
        "Nessun articolo trovato per 'multimetro' nella categoria 'sensori'.")


def test_catalogo_vuoto(tmp_path):
    assert _cerca(_scrivi(tmp_path / "c.csv", []), testo="x") == (
        "Nessun articolo trovato per 'x'. Categorie disponibili: nessuna.")


# --- dettaglio -------------------------------------------------------------------------------

@pytest.mark.parametrize("codice", ["MUL-01", "mul-01", " MUL-01 "])
def test_dettaglio(catalogo, codice):
    assert _cerca(catalogo, codice=codice) == (
        "Articolo MUL-01:\n"
        "- nome: Multimetro digitale\n"
        "- categoria: misura\n"
        "- descrizione: Tensione, corrente e resistenza\n"
        "- ubicazione: Armadio A, ripiano 2\n"
        "- quantità disponibile: 6")


def test_dettaglio_codice_inesistente(catalogo):
    assert _cerca(catalogo, codice="XYZ-99") == "Nessun articolo con codice 'XYZ-99'."


# --- errori sugli argomenti ------------------------------------------------------------------

@pytest.mark.parametrize("argomenti", [{}, {"testo": "  ", "categoria": "", "codice": " "}])
def test_nessun_criterio(catalogo, argomenti):
    assert _cerca(catalogo, **argomenti).startswith("Errore: indica cosa cercare")


@pytest.mark.parametrize("argomenti", [{"codice": "MUL-01", "testo": "multimetro"},
                                       {"codice": "MUL-01", "categoria": "misura"}])
def test_codice_insieme_alla_ricerca(catalogo, argomenti):
    assert _cerca(catalogo, **argomenti).startswith("Errore: usa codice da solo")


def test_testo_troppo_lungo(catalogo):
    assert _cerca(catalogo, testo="a" * 101) == "Errore: testo troppo lungo (massimo 100 caratteri)."


def test_categoria_inesistente(catalogo):
    assert _cerca(catalogo, categoria="ottica") == (
        "Errore: categoria inesistente: 'ottica'. Categorie disponibili: alimentazione, misura, sensori.")


# --- file mancante o rovinato ----------------------------------------------------------------

@pytest.mark.parametrize("intestazione, righe", [
    ("codice,nome,categoria,descrizione,ubicazione,quantita", []),           # separatore sbagliato
    ("codice;nome;categoria;ubicazione;quantita", []),                      # colonna mancante
    (INTESTAZIONE, ["MUL-01;A;misura;d;u;1", "mul-01;B;misura;d;u;2"]),     # codice duplicato
    (INTESTAZIONE, ["MUL-01;A;misura;d;u;tanti"]),                          # quantità non numerica
    (INTESTAZIONE, ["MUL-01;A;misura;d;u;-1"]),                             # quantità negativa
    (INTESTAZIONE, ["MUL-01;A;misura;d;u"]),                                # campo mancante
    (INTESTAZIONE, ["MUL-01;A;misura;d;u;1;extra"]),                        # campo in più
    (INTESTAZIONE, [";A;misura;d;u;1"]),                                    # codice vuoto
])
def test_file_rovinato(tmp_path, intestazione, righe):
    percorso = _scrivi(tmp_path / "c.csv", righe, intestazione)
    assert _cerca(percorso, testo="a") == "Errore: catalogo non disponibile o non valido."


def test_file_mancante(tmp_path):
    assert _cerca(tmp_path / "manca.csv", codice="X") == "Errore: catalogo non disponibile o non valido."


def test_file_con_bom_di_excel(tmp_path):
    percorso = _scrivi(tmp_path / "c.csv", RIGHE, codifica="utf-8-sig")
    assert "MUL-01" in _cerca(percorso, codice="MUL-01")


# --- file del progetto -----------------------------------------------------------------------

def test_catalogo_del_progetto_valido():
    with open(PERCORSO_CATALOGO, encoding="utf-8-sig", newline="") as f:
        righe = list(csv.DictReader(f, delimiter=";"))
    assert tuple(righe[0]) == COLONNE and len(righe) >= 15
    assert "Errore" not in cerca_nel_catalogo(testo="multimetro")
    assert cerca_nel_catalogo(testo="microscopio").startswith("Nessun articolo trovato")


# --- strumento e grafo -----------------------------------------------------------------------

def test_strumento_langchain(catalogo):
    strumento = crea_strumento_catalogo(catalogo)
    assert strumento.name == "catalogo_locale"
    schema = strumento.args_schema.model_json_schema()
    assert set(schema["properties"]) == {"testo", "categoria", "codice"}
    assert schema.get("required", []) == []
    assert strumento.invoke({"codice": "OSC-01"}).startswith("Articolo OSC-01:")


def test_ciclo_completo_nel_grafo(catalogo):
    richiesta = AIMessage("", tool_calls=[
        {"name": "catalogo_locale", "args": {"testo": "microscopio"}, "id": "c1"}])
    m = ModelloFinto(risposte=[richiesta, AIMessage("No, in catalogo non c'è un microscopio.")])
    out = costruisci_grafo(m, [crea_strumento_catalogo(catalogo)], 3).invoke(
        {"messages": [HumanMessage("Avete un microscopio?")], "passaggi": 0})
    risultati = [t.content for t in out["messages"] if isinstance(t, ToolMessage)]
    assert risultati == ["Nessun articolo trovato per 'microscopio'. "
                         "Categorie disponibili: alimentazione, misura, sensori."]
