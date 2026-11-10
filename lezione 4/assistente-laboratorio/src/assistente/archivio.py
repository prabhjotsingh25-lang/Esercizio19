"""Archivio del back-end: conversazioni e messaggi. In memoria (test) o su PostgreSQL (pg8000).

Le due versioni hanno la stessa interfaccia e passano le stesse prove (tests/test_archivio.py).
"""
import json
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from importlib import resources
from itertools import count
from typing import Protocol
from urllib.parse import urlparse
from uuid import UUID, uuid4

MESSAGGIO_INTERROTTO = "turno interrotto da un arresto del back-end: riprova"


@dataclass(frozen=True)
class Conversazione:
    id: str
    titolo: str | None
    creata: datetime
    aggiornata: datetime
    preferenze: dict
    riassunto: str = ""
    cronologia_agente: list = field(default_factory=list)
    turno_in_corso: bool = False


@dataclass(frozen=True)
class Messaggio:
    id: int
    conversazione_id: str
    posizione: int
    ruolo: str
    testo: str
    strumenti: list | None = None
    prompt: dict | None = None
    stato: str | None = None
    errore: str | None = None
    creato: datetime | None = None


class Archivio(Protocol):
    def crea(self, preferenze: dict) -> Conversazione: ...
    def leggi(self, id: str) -> Conversazione | None: ...
    def elenca(self) -> list[Conversazione]: ...
    def elimina(self, id: str) -> bool: ...
    def messaggi(self, id: str) -> list[Messaggio]: ...
    def aggiungi(self, id: str, ruolo: str, testo: str, *, strumenti: list | None = None,
                 prompt: dict | None = None, stato: str | None = None) -> Messaggio: ...
    def aggiorna_domanda(self, id_messaggio: int, *, stato: str, testo: str | None = None,
                         errore: str | None = None) -> None: ...
    def elimina_messaggio(self, id_messaggio: int) -> None: ...
    def salva_stato_agente(self, id: str, cronologia: list, riassunto: str) -> None: ...
    def imposta_titolo(self, id: str, titolo: str) -> None: ...
    def aggiorna_preferenze(self, id: str, preferenze: dict) -> None: ...
    def inizia_turno(self, id: str) -> bool: ...
    def fine_turno(self, id: str) -> None: ...
    def azzera_turni(self) -> None: ...
    def ping(self) -> str | None: ...


def _adesso() -> datetime:
    return datetime.now(timezone.utc)


class ArchivioMemoria:
    """Archivio per i test offline: dizionari protetti da un lock."""

    def __init__(self):
        self._lock = threading.Lock()
        self._conversazioni: dict[str, Conversazione] = {}
        self._messaggi: dict[int, Messaggio] = {}
        self._id = count(1)

    def crea(self, preferenze):
        with self._lock:
            adesso = _adesso()
            c = Conversazione(str(uuid4()), None, adesso, adesso, dict(preferenze))
            self._conversazioni[c.id] = c
            return c

    def leggi(self, id):
        return self._conversazioni.get(str(id))

    def elenca(self):
        return sorted(self._conversazioni.values(), key=lambda c: c.aggiornata, reverse=True)

    def elimina(self, id):
        with self._lock:
            if self._conversazioni.pop(str(id), None) is None:
                return False
            for k in [k for k, m in self._messaggi.items() if m.conversazione_id == str(id)]:
                del self._messaggi[k]
            return True

    def messaggi(self, id):
        return sorted((m for m in self._messaggi.values() if m.conversazione_id == str(id)),
                      key=lambda m: m.posizione)

    def aggiungi(self, id, ruolo, testo, *, strumenti=None, prompt=None, stato=None):
        with self._lock:
            posizione = 1 + max((m.posizione for m in self._messaggi.values()
                                 if m.conversazione_id == id), default=0)
            m = Messaggio(next(self._id), id, posizione, ruolo, testo, strumenti, prompt, stato,
                          None, _adesso())
            self._messaggi[m.id] = m
            self._conversazioni[id] = replace(self._conversazioni[id], aggiornata=m.creato)
            return m

    def aggiorna_domanda(self, id_messaggio, *, stato, testo=None, errore=None):
        with self._lock:
            m = self._messaggi[id_messaggio]
            self._messaggi[id_messaggio] = replace(m, stato=stato, errore=errore,
                                                   testo=m.testo if testo is None else testo)

    def elimina_messaggio(self, id_messaggio):
        with self._lock:
            self._messaggi.pop(id_messaggio, None)

    def _cambia(self, id, **campi):
        with self._lock:
            self._conversazioni[id] = replace(self._conversazioni[id], **campi)

    def salva_stato_agente(self, id, cronologia, riassunto):
        self._cambia(id, cronologia_agente=list(cronologia), riassunto=riassunto)

    def imposta_titolo(self, id, titolo):
        if self._conversazioni[id].titolo is None:
            self._cambia(id, titolo=titolo)

    def aggiorna_preferenze(self, id, preferenze):
        self._cambia(id, preferenze=dict(preferenze))

    def inizia_turno(self, id):
        with self._lock:
            c = self._conversazioni[id]
            if c.turno_in_corso:
                return False
            self._conversazioni[id] = replace(c, turno_in_corso=True)
            return True

    def fine_turno(self, id):
        if id in self._conversazioni:
            self._cambia(id, turno_in_corso=False)

    def azzera_turni(self):
        with self._lock:
            for k, c in self._conversazioni.items():
                self._conversazioni[k] = replace(c, turno_in_corso=False)
            for k, m in self._messaggi.items():
                if m.stato == "in_attesa":
                    self._messaggi[k] = replace(m, stato="errore", errore=MESSAGGIO_INTERROTTO)

    def ping(self):
        return None


class ArchivioPostgres:
    """Archivio su PostgreSQL con pg8000 (Python puro) e SQL scritto a mano.

    Una connessione per operazione: semplice e sicuro con le richieste servite in thread diversi.
    """

    def __init__(self, url: str):
        self._parametri = self._da_url(url)
        schema = resources.files("assistente").joinpath("schema.sql").read_text(encoding="utf-8")
        righe = [r for r in schema.splitlines() if not r.lstrip().startswith("--")]
        with self._connessione() as c:
            for istruzione in "\n".join(righe).split(";"):
                if istruzione.strip():
                    c.run(istruzione)

    @staticmethod
    def _da_url(url: str) -> dict:
        u = urlparse(url)
        return {"user": u.username, "password": u.password, "host": u.hostname or "127.0.0.1",
                "port": u.port or 5432, "database": (u.path or "/").lstrip("/") or u.username}

    def _connessione(self):
        import pg8000.native
        return pg8000.native.Connection(**self._parametri, timeout=10)

    @classmethod
    def crea_database(cls, url: str) -> None:
        """Crea il database di `url` se manca (serve un utente con il permesso CREATEDB)."""
        import pg8000.native
        parametri = cls._da_url(url)
        nome = parametri["database"]
        with pg8000.native.Connection(**{**parametri, "database": "postgres"}, timeout=10) as c:
            if not c.run("SELECT 1 FROM pg_database WHERE datname = :n", n=nome):
                c.run(f'CREATE DATABASE "{nome}"')

    def svuota(self) -> None:
        """Solo per le prove: cancella tutti i dati."""
        with self._connessione() as c:
            c.run("TRUNCATE messaggi, conversazioni")

    @staticmethod
    def _conversazione(riga) -> Conversazione:
        id, titolo, creata, aggiornata, preferenze, riassunto, cronologia, turno = riga
        return Conversazione(str(id), titolo, creata, aggiornata, preferenze, riassunto,
                             cronologia, turno)

    _CAMPI_C = ("id, titolo, creata, aggiornata, preferenze, riassunto, cronologia_agente, "
                "turno_in_corso")
    _CAMPI_M = ("id, conversazione_id, posizione, ruolo, testo, strumenti, prompt, stato, "
                "errore, creato")

    @staticmethod
    def _messaggio(riga) -> Messaggio:
        id, conv, pos, ruolo, testo, strumenti, prompt, stato, errore, creato = riga
        return Messaggio(id, str(conv), pos, ruolo, testo, strumenti, prompt, stato, errore, creato)

    @staticmethod
    def _uuid(id: str) -> str | None:
        try:
            return str(UUID(str(id)))
        except ValueError:
            return None

    def crea(self, preferenze):
        with self._connessione() as c:
            riga = c.run(f"INSERT INTO conversazioni (id, preferenze) VALUES (:id, CAST(:p AS jsonb)) "
                         f"RETURNING {self._CAMPI_C}", id=str(uuid4()), p=json.dumps(preferenze))[0]
        return self._conversazione(riga)

    def leggi(self, id):
        if self._uuid(id) is None:
            return None
        with self._connessione() as c:
            righe = c.run(f"SELECT {self._CAMPI_C} FROM conversazioni WHERE id = CAST(:id AS uuid)",
                          id=str(id))
        return self._conversazione(righe[0]) if righe else None

    def elenca(self):
        with self._connessione() as c:
            righe = c.run(f"SELECT {self._CAMPI_C} FROM conversazioni ORDER BY aggiornata DESC")
        return [self._conversazione(r) for r in righe]

    def elimina(self, id):
        if self._uuid(id) is None:
            return False
        with self._connessione() as c:
            return bool(c.run("DELETE FROM conversazioni WHERE id = CAST(:id AS uuid) RETURNING id",
                              id=str(id)))

    def messaggi(self, id):
        with self._connessione() as c:
            righe = c.run(f"SELECT {self._CAMPI_M} FROM messaggi WHERE conversazione_id = "
                          "CAST(:id AS uuid) ORDER BY posizione", id=str(id))
        return [self._messaggio(r) for r in righe]

    def aggiungi(self, id, ruolo, testo, *, strumenti=None, prompt=None, stato=None):
        with self._connessione() as c:
            riga = c.run(
                f"INSERT INTO messaggi (conversazione_id, posizione, ruolo, testo, strumenti, prompt, "
                "stato) SELECT CAST(:id AS uuid), COALESCE(MAX(posizione), 0) + 1, :ruolo, :testo, "
                "CAST(:strumenti AS jsonb), CAST(:prompt AS jsonb), :stato FROM messaggi "
                f"WHERE conversazione_id = CAST(:id AS uuid) RETURNING {self._CAMPI_M}",
                id=str(id), ruolo=ruolo, testo=testo, stato=stato,
                strumenti=None if strumenti is None else json.dumps(strumenti),
                prompt=None if prompt is None else json.dumps(prompt))[0]
            c.run("UPDATE conversazioni SET aggiornata = :t WHERE id = CAST(:id AS uuid)",
                  t=riga[-1], id=str(id))
        return self._messaggio(riga)

    def aggiorna_domanda(self, id_messaggio, *, stato, testo=None, errore=None):
        with self._connessione() as c:
            c.run("UPDATE messaggi SET stato = :stato, errore = :errore, "
                  "testo = COALESCE(:testo, testo) WHERE id = :id",
                  stato=stato, errore=errore, testo=testo, id=id_messaggio)

    def elimina_messaggio(self, id_messaggio):
        with self._connessione() as c:
            c.run("DELETE FROM messaggi WHERE id = :id", id=id_messaggio)

    def salva_stato_agente(self, id, cronologia, riassunto):
        with self._connessione() as c:
            c.run("UPDATE conversazioni SET cronologia_agente = CAST(:c AS jsonb), riassunto = :r "
                  "WHERE id = CAST(:id AS uuid)", c=json.dumps(cronologia), r=riassunto, id=str(id))

    def imposta_titolo(self, id, titolo):
        with self._connessione() as c:
            c.run("UPDATE conversazioni SET titolo = :t WHERE id = CAST(:id AS uuid) "
                  "AND titolo IS NULL", t=titolo, id=str(id))

    def aggiorna_preferenze(self, id, preferenze):
        with self._connessione() as c:
            c.run("UPDATE conversazioni SET preferenze = CAST(:p AS jsonb) "
                  "WHERE id = CAST(:id AS uuid)", p=json.dumps(preferenze), id=str(id))

    def inizia_turno(self, id):
        with self._connessione() as c:
            return bool(c.run("UPDATE conversazioni SET turno_in_corso = true WHERE id = "
                              "CAST(:id AS uuid) AND NOT turno_in_corso RETURNING id", id=str(id)))

    def fine_turno(self, id):
        with self._connessione() as c:
            c.run("UPDATE conversazioni SET turno_in_corso = false WHERE id = CAST(:id AS uuid)",
                  id=str(id))

    def azzera_turni(self):
        with self._connessione() as c:
            c.run("UPDATE conversazioni SET turno_in_corso = false WHERE turno_in_corso")
            c.run("UPDATE messaggi SET stato = 'errore', errore = :e WHERE stato = 'in_attesa'",
                  e=MESSAGGIO_INTERROTTO)

    def ping(self):
        try:
            with self._connessione() as c:
                c.run("SELECT 1")
        except Exception as errore:  # connessione rifiutata, credenziali, timeout
            return f"database non raggiungibile su {self._parametri['host']}:" \
                   f"{self._parametri['port']} ({errore})"
        return None
