# Piano · Step 4 Preferenze (resource MCP)

Branch `feat/preferenze` da `dev`. Specifica: `../specs/2026-11-10-preferenze-design.md`.

1. `preferenze.py` (TDD): schema a tre campi validati, `da_json`, lettura del file, predefinite
   con WARNING, testo per il prompt.
2. `server_mcp.py` e `variante_mcp.py` (TDD, client in memoria e finto): resource
   `utente://preferenze`, lettore MCP con errori leggibili; la resource non è fra i tool.
3. `grafo.py`, `revisore.py`, `sessione.py` (TDD): campo `preferenze` nello stato, in cima al
   messaggio di sistema, al revisore e non al router; lettura a inizio sessione e con `/nuova`.
4. `config.py` (`PREFERENZE_FILE`), `varianti.py` (lettore per variante), `cli.py`;
   `preferenze.example.json`, `.gitignore`, `.env.example`.
5. Prove reali: CLI variante `mcp` con `America/New_York` (log della `resources/read`),
   fuso predefinito, lingua e stile dalla sessione successiva, router.
6. README e CLAUDE.md; evidenze e proposta di commit, poi stop.
