-- Schema del back-end (step 7). Applicato all'avvio: CREATE ... IF NOT EXISTS, nessuna migrazione.
CREATE TABLE IF NOT EXISTS conversazioni (
    id                uuid PRIMARY KEY,
    titolo            text,                              -- prime parole della prima domanda
    creata            timestamptz NOT NULL DEFAULT now(),
    aggiornata        timestamptz NOT NULL DEFAULT now(), -- data dell'ultimo messaggio
    preferenze        jsonb NOT NULL,                    -- lingua, fuso_orario, stile
    riassunto         text NOT NULL DEFAULT '',          -- stato dell'agente, così come restituito
    cronologia_agente jsonb NOT NULL DEFAULT '[]',       -- stato dell'agente, così come restituito
    turno_in_corso    boolean NOT NULL DEFAULT false     -- un solo turno alla volta
);

CREATE TABLE IF NOT EXISTS messaggi (
    id               bigserial PRIMARY KEY,
    conversazione_id uuid NOT NULL REFERENCES conversazioni (id) ON DELETE CASCADE,
    posizione        integer NOT NULL,
    ruolo            text NOT NULL CHECK (ruolo IN ('utente', 'assistente')),
    testo            text NOT NULL,
    strumenti        jsonb,  -- risposte: strumenti usati (nome, argomenti, risultato)
    prompt           jsonb,  -- domande da /prompt: nome e argomenti
    stato            text CHECK (stato IN ('in_attesa', 'risposta', 'errore')),  -- domande
    errore           text,   -- domande in errore: messaggio dell'agente
    creato           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (conversazione_id, posizione)
);
