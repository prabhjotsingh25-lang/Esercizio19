"""compose.yaml (step 9): servizi, indirizzi, porte, dipendenze e segreti fuori dal file.

Usa PyYAML, già presente nel venv come dipendenza indiretta; solo nei test.
"""
from pathlib import Path

import yaml

COMPOSE = Path(__file__).parent.parent / "compose.yaml"
TESTO = COMPOSE.read_text(encoding="utf-8")
SERVIZI = yaml.safe_load(TESTO)["services"]


def _env(nome):
    return SERVIZI[nome].get("environment", {})


def test_servizi_dell_applicazione_e_profili():
    assert {"postgres", "agente", "backend", "frontend"} <= set(SERVIZI)
    for nome in ("postgres", "agente", "backend", "frontend"):
        assert "profiles" not in SERVIZI[nome], f"{nome} deve partire con docker compose up"
    assert SERVIZI["assistente"]["profiles"] == ["cli"]
    assert SERVIZI["strumenti-http"]["profiles"] == ["http"]
    assert SERVIZI["strumenti-mcp"]["profiles"] == ["mcp"]


def test_ascolto_su_tutte_le_interfacce_nei_container():
    assert _env("agente")["AGENTE_HOST"] == "0.0.0.0"
    assert _env("backend")["BACKEND_HOST"] == "0.0.0.0"
    assert _env("frontend")["FRONTEND_HOST"] == "0.0.0.0"


def test_indirizzi_interni_e_quelli_del_browser():
    assert _env("backend")["AGENTE_URL"] == "http://agente:8000"
    assert "@postgres:5432/" in _env("backend")["DATABASE_URL"]
    # visti dal browser sull'host: stesso nome (localhost) perché il CORS combaci
    assert _env("frontend")["BACKEND_URL"] == "http://localhost:8080"
    assert _env("backend")["FRONTEND_ORIGINE"] == "http://localhost:8090"
    assert _env("agente")["LMSTUDIO_BASE_URL"] == "http://host.docker.internal:1234/v1"


def test_porte_pubblicate_solo_su_127_0_0_1_e_solo_back_end_e_front_end():
    assert SERVIZI["backend"]["ports"] == ["127.0.0.1:8080:8080"]
    assert SERVIZI["frontend"]["ports"] == ["127.0.0.1:8090:8090"]
    for nome in ("postgres", "agente"):
        assert "ports" not in SERVIZI[nome], f"{nome} non deve essere raggiungibile dall'host"


def test_avvio_in_ordine_e_dati_persistenti():
    assert SERVIZI["backend"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert "pg_isready" in " ".join(SERVIZI["postgres"]["healthcheck"]["test"])
    assert "pgdati:/var/lib/postgresql/data" in SERVIZI["postgres"]["volumes"]


def test_nessuna_password_scritta_nel_file():
    assert "${POSTGRES_PASSWORD" in TESTO
    assert _env("postgres")["POSTGRES_PASSWORD"].startswith("${POSTGRES_PASSWORD")
    assert "${POSTGRES_PASSWORD}" in _env("backend")["DATABASE_URL"]
