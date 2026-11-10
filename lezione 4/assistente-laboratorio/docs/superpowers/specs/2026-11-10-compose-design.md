# Step 9 · Docker Compose: applicazione completa

Ultimo dei nove step. Approvato dall'utente il 2026-11-10.

## Obiettivo
Un solo `docker compose up -d --build` avvia l'applicazione completa (PostgreSQL, agente, back-end,
front-end); LM Studio resta sull'host. La chat si apre su `http://localhost:8090`.

## Decisioni
- **Servizi**: `postgres` (postgres:16, volume `pgdati`, healthcheck `pg_isready`, nessuna porta
  sull'host); `agente` (`python -m assistente.servizio_agente`, variante `locale`, nessuna porta
  sull'host); `backend` (`python -m assistente.backend`, porta `127.0.0.1:8080`); `frontend`
  (`python -m assistente.frontend`, porta `127.0.0.1:8090`). Stessa immagine (`Dockerfile`
  invariato), comandi diversi. La CLI (`assistente`) passa al profilo `cli` e si avvia ancora con
  `docker compose run --rm assistente`; `strumenti-http` e `strumenti-mcp` restano nei profili.
- **Indirizzi**: nei container si ascolta su `0.0.0.0`; i servizi si parlano con i nomi di Compose
  (`AGENTE_URL=http://agente:8000`, `DATABASE_URL=...@postgres:5432/...`). `BACKEND_URL` e
  `FRONTEND_ORIGINE` sono visti dal browser: `http://localhost:8080` e `http://localhost:8090`
  (stesso nome, perché il CORS combaci).
- **Segreti**: `POSTGRES_PASSWORD` solo nel `.env`, interpolata da Compose; nessuna password nel
  file.
- **Ordine**: il back-end parte quando PostgreSQL è pronto (`service_healthy`) e dopo l'agente.
- **Separazione**: il PostgreSQL di Compose è diverso da quello avviato a mano (porta 55432) e
  non pubblica porte, quindi non va in conflitto con la 5432 occupata sull'host.
- **Preferenze**: nei container non c'è `preferenze.json` → predefinite con WARNING (montare il
  file è rimandato: se manca, Docker crea una cartella al suo posto).

## Verifiche
- Offline: test su `compose.yaml` (servizi, profili, host `0.0.0.0`, indirizzi interni e del
  browser, porte solo su `127.0.0.1`, healthcheck, password fuori dal file); `docker compose config`.
- Reali: `up -d --build`, `/stato` del back-end, conversazione con strumento nel browser (Edge
  senza finestra), `restart backend` e `down`/`up` con la chat ancora presente.
