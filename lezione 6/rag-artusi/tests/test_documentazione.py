"""La documentazione elenca gli stessi campi del payload che il codice produce."""

import re
from pathlib import Path

from rag.chunking import crea_chunk
from rag.corpus import Ricetta
from tests.conftest import crea_config

README = Path(__file__).resolve().parent.parent / "README.md"


def test_readme_elenca_tutti_i_campi_del_payload():
    (chunk,) = crea_chunk([Ricetta(1, "Brodo", "Brodi, gelatina e sughi", "Testo.")], crea_config())
    testo = README.read_text(encoding="utf-8")
    inizio = testo.index("Payload di ogni punto:")
    elenco = testo[inizio : testo.index("\n\n", inizio)]
    assert set(re.findall(r"`([a-z_]+)`", elenco)) == set(chunk.payload)
