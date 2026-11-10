# Piano · Fix revisore (strumenti e riassunto)

Branch `fix/revisore-strumenti` da `dev`. Specifica: `../specs/2026-11-10-fix-revisore-design.md`.

1. `tests/test_revisore.py` (TDD): prompt con riassunto, strumenti del turno corrente soltanto,
   taglio a 500 caratteri, «(nessuno)», istruzioni sui dati attendibili.
2. `tests/test_grafo.py` (TDD): il revisore riceve il riassunto dallo stato; revisore simulato
   che giudica dal prompt vero: risposta basata su strumento e nome dal riassunto non bocciati.
3. `revisore.py` (firma, prompt, istruzioni) e `grafo.py` (riassunto al revisore).
4. Prove reali veloci (revisore vero su messaggi preparati); se passano, flusso completo con
   «Che ore sono a Tokyo?» nella prova di compressione; poi prove del router.
5. CLAUDE.md (via la voce dal «Debito noto»), README, note della specifica dello step 3;
   evidenze e proposta di commit, poi attesa dell'ok per il merge.
