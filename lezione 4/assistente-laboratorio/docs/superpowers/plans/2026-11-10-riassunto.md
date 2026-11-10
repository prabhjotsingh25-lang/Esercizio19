# Piano · Step 3 Riassunto

Branch `feat/riassunto` da `dev`. Specifica: `../specs/2026-11-10-riassunto-design.md`.

1. Specifica approvata, commit `docs:`.
2. `config.py` (TDD): `SOGLIA_RIASSUNTO` (default 20) e `MESSAGGI_RECENTI` (default 6), interi
   >= 1, con `MESSAGGI_RECENTI` < `SOGLIA_RIASSUNTO`; `.env.example`.
3. `riassunto.py` (TDD): `punto_di_taglio` (solo tra turni, mai fra tool call e `ToolMessage`),
   dialogo da riassumere senza indicazioni, bozze scartate e strumenti, `crea_riassuntore`.
4. `grafo.py` (TDD, modelli simulati): campo `riassunto`, nodo `riassunto` all'inizio con
   `RemoveMessage`, nessuna chiamata sotto soglia, riassunto nel messaggio di sistema
   dell'agente e nel contesto del router (`router(messaggi, riassunto)`), riassunto vuoto →
   nessun taglio con WARNING; limite di ricorsione +1.
5. `sessione.py` e `cli.py`: il riassunto passa da un turno all'altro, `/nuova` lo azzera.
6. Prove reali (`SOGLIA_RIASSUNTO=6`, `MESSAGGI_RECENTI=2`): nome al turno 1, compressione con
   log, «come mi chiamo?» dopo la compressione; sotto soglia nessuna chiamata. Rilancio delle
   prove del router e di «note con conferma».
7. README e CLAUDE.md; evidenze e proposta di commit, poi attesa di «avanti».
