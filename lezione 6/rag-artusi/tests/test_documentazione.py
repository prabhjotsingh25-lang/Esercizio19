"""La documentazione elenca gli stessi campi del payload che il codice produce."""

import re
from pathlib import Path

from rag.chunking import crea_chunk
from rag.corpus import Ricetta
from tests.conftest import crea_config

README = Path(__file__).resolve().parent.parent / "README.md"


def test_specifica_b_descrive_la_sequenza_reale_di_in_aggiornamento():
    """Il comportamento è verificato da test_errore_negli_embedding_non_tocca_la_collezione e
    test_interruzione_durante_la_scrittura_lascia_in_aggiornamento; qui si controlla che i documenti lo dicano."""
    docs = README.parent / "docs"
    spec = " ".join((docs / "specs" / "modifica-b.md").read_text(encoding="utf-8").split())
    piano = " ".join((docs / "plans" / "modifica-b.md").read_text(encoding="utf-8").split())
    assert "subito prima della scrittura" in spec
    assert "Embedder che fallisce → collezione intatta" in spec
    assert "embedder che fallisce) → il metadato resta `in_aggiornamento`" not in spec
    assert "embedder che fallisce → collezione intatta" in piano
    assert "interruzione (embedder che fallisce) → metadato" not in piano


def test_readme_elenca_tutti_i_campi_del_payload():
    (chunk,) = crea_chunk([Ricetta(1, "Brodo", "Brodi, gelatina e sughi", "Testo.")], crea_config())
    testo = README.read_text(encoding="utf-8")
    inizio = testo.index("Payload di ogni punto:")
    elenco = testo[inizio : testo.index("\n\n", inizio)]
    assert set(re.findall(r"`([a-z_]+)`", elenco)) == set(chunk.payload)
