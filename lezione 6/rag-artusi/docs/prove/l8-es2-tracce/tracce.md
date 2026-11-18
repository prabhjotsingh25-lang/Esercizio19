# Lezione 8 · Es. 2 — tracce dei quattro casi

- Data: 2026-11-18 10:17 · modello `google/gemma-4-e2b` · variante strumenti `locale` · server MCP da `server_mcp.json`
- Comando (da `lezione 4/assistente-laboratorio`): `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.prove_rag --uscita <cartella>`

| Caso | Domanda | Atteso | Strumenti | Citazioni verificate / sconosciute | Esito | Durata |
|---|---|---|---|---|---|---|
| documentale | Quanta farina serve per 400 grammi di patate negli gnocchi? | ricerca chiamata, citazioni tutte verificate | search_documents | 89.0 / - | **atteso** | 313.0 s |
| ora | Che ore sono a Tokyo? | orologio, non ricerca | ora_corrente | - / - | **atteso** | 109.6 s |
| generica | Ciao! Cosa sai fare? | nessuno strumento | nessuno | - / - | **atteso** | 116.1 s |
| senza_risposta | Qual è la ricetta del tiramisù? | ricerca chiamata, astensione, nessuna citazione | search_documents | - / - | **atteso** | 215.0 s |

## documentale: «Quanta farina serve per 400 grammi di patate negli gnocchi?»

- Atteso: ricerca chiamata, citazioni tutte verificate → **atteso**
- Strumento `search_documents` {"query": "farina per gnocchi patate"} → modalità base, passaggi: 89.0 (Gnocchi di patate, 0.775), 89.1 (Gnocchi di patate, 0.742), 90.0 (Gnocchi di farina gialla, 0.735), 201.0 (Pallottole di patate ripiene, 0.721), 661.1 (Budino di patate, 0.71)

Risposta:

> Per 400 grammi di patate, secondo la ricetta trovata, servono 150 grammi di farina di grano per gli gnocchi [89.0].

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La richiesta riguarda un calcolo di quantità specifico relativo a una ricetta culinaria. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo strumento passaggio=1 nome=search_documents argomenti={'query': 'farina per gnocchi patate'} risultato={"modalita":"base","query_usate":["farina per gnocchi patate"],"passaggi":[{"id":"89.0","ricetta":89,"titolo":"Gnocchi di patate","capitolo":"Minestre asciutte e di magro","posizione_chunk":0,"score":0.775,"testo":"La famiglia de' gnocchi è numerosa. Vi ho già descritto gli gnocchi in brodo del N. 14: ora v'indicherò gli gnocchi di patate e di farina gialla per minestra e più avanti quelli di semolino e alla romana per tramesso o per contorno, e quelli di latte per dolce. Patate grosse e gialle, grammi 400. Farina di grano, grammi 150. Vi noto la proporzione della farina per intriderli, onde non avesse ad accadervi come ad una signora che, me presente, appena affondato il mestolo per muoverli nella pentola non trovò più nulla; gli gnocchi erano spariti. — O dov'erano andati? — mi domandò con premurosa curiosità un'altra signora, a cui per ridere raccontai il fatto, credendo forse che il folletto li avesse portati via. — Non inarchi le ciglia, signora — risposi io — chè lo strano fenomeno è naturale:…"},{"id":"89.1","ricetta":89,"titolo":"Gnocchi di patate","capitolo":"Minestre asciutte e di magro","posizione_chunk":1,"score":0.742,"testo":"portati via. — Non inarchi le ciglia, signora — risposi io — chè lo strano fenomeno è naturale: quelli gnocchi erano stati intrisi con poca farina e appena furono nell'acqua bollente si liquefecero. — Cuocete le patate nell'acqua o, meglio, a vapore e, calde bollenti, spellatele e passatele per istaccio. Poi intridetele colla detta farina e lavorate alquanto l'impasto colle mani, tirandolo a cilindro sottile per poterlo tagliare a tocchetti lunghi tre centimetri circa. Spolverizzateli leggermente di farina e, prendendoli uno alla volta, scavateli col pollice sul rovescio di una grattugia. Metteteli a cuocere nell'acqua salata per dieci minuti, levateli asciutti e conditeli con cacio, burro e sugo di pomodoro, piacendovi. Se li volete più delicati cuoceteli nel latte e serviteli senza scol…"},{"id":"90.0","ricetta":90,"titolo":"Gnocchi di farina gialla","capitolo":"Minestre asciutte e di magro","posizione_chunk":0,"score":0.735,"testo":"Quando vi sentite una certa ripienezza prodotta da esuberanza di nutrizione, se ricorrete a una minestra di questi gnocchi potrete, per la loro leggerezza e poca sostanza, neutralizzarla; e più ancora se farete seguire ad essa un piatto di pesce di facile digestione. La farina, per quest'uso, è bene sia macinata grossa; se no è meglio ricorrere al semolino fine di granturco, che ora trovasi in commercio. Salate l'acqua e, quando bolle, versate colla mano sinistra la farina un po' per volta e col mestolo nella destra, mescolate continuamente. È necessario che questa farina bolla molto, e quando essa è ristretta in modo da reggere bene sul mestolo, gettatela, con un coltello da tavola, a tocchetti entro a un vassoio e ad ogni strato conditela con cacio, burro, sugo di pomodoro o conserva sc…"},{"id":"201.0","ricetta":201,"titolo":"Pallottole di patate ripiene","capitolo":"Fritti","posizione_chunk":0,"score":0.721,"testo":"Patate, grammi 300. Parmigiano, due cucchiaiate ben colme. Uova, N. 2. Odore di noce moscata. Farina, quanto basta. Lessate le patate, sbucciatele e passatele calde dallo staccio sopra a un velo di farina. Fate una buca sul monte delle patate, salatele, date loro l'odore della noce moscata e versateci le uova e il parmigiano. Poi, con meno farina che potete, formatene un pastone morbido e lungo che dividerete in 18 parti e ad ognuna di queste, con le dita infarinate, fate una piccola buca per riempirla con un battuto di carne. Tirateci sopra i lembi per coprirlo e, con le mani infarinate, formate palle rotonde che friggerete nello strutto o nell'olio, mandandole in tavola per contorno a un fritto di carne. È un piatto appariscente, buono e di poca spesa perchè il ripieno potete formarlo a…"},{"id":"661.1","ricetta":661,"titolo":"Budino di patate","capitolo":"Torte e dolci al cucchiaio","posizione_chunk":1,"score":0.71,"testo":"ai muscoli. Patate grosse farinacee, grammi 700. Zucchero, grammi 150. Burro, grammi 40. Farina, grammi 20. Latte, decilitri 2. Uova, N. 6. Una presa di sale. Odore di cannella o di scorza di limone. Cuocete le patate nell'acqua o a vapore, sbucciatele e passatele calde dallo staccio. Rimettetele al fuoco col burro, la farina e il latte, versato a poco per volta, lavorandole bene col mestolo; indi aggiungete lo zucchero, il sale e l'odore e lasciatele stare tanto che s'incorporino bene insieme tutte queste cose. Ritirate dal fuoco, quando saranno tiepide o diacce, gettateci i rossi e poi le chiare montate. Cuocetelo come tutti gli altri budini; cioè nel fornello o nel forno e servitelo caldo."}],"nota":""}
INFO assistente.grafo agente: chiamata al modello con 4 messaggi
INFO assistente.grafo revisore coerente=sì motivo=La risposta è coerente con i dati forniti dallo strumento di ricerca, estraendo la quantità richiesta dalla ricetta trovata. -> fine
INFO assistente.agente citazioni verificate=89.0 sconosciute=- ricerche=1 passaggi_ricevuti=5
```

Log del server di ricerca:

```
2026-11-18 10:07:36,030 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi top_k_max=10
2026-11-18 10:07:43,129 INFO rag.server_mcp ricerca esito=ok modalita=base query="farina per gnocchi patate" top_k=5 filtro=- passaggi=5 ids=89.0,89.1,90.0,201.0,661.1 nota="" ms=6283
```

## ora: «Che ore sono a Tokyo?»

- Atteso: orologio, non ricerca → **atteso**
- Strumento `ora_corrente` {"fuso_orario": "Asia/Tokyo"} → 2026-11-18T18:11:25+09:00 (Asia/Tokyo)

Risposta:

> Attualmente a Tokyo sono le ore 18:11:25 del 18 novembre 2026.

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La richiesta riguarda la conversione di un orario tra diversi fusi orari, rientrando nell'ambito della gestione dati e del tempo. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo strumento passaggio=1 nome=ora_corrente argomenti={'fuso_orario': 'Asia/Tokyo'} risultato=2026-11-18T18:11:25+09:00 (Asia/Tokyo)
INFO assistente.grafo agente: chiamata al modello con 4 messaggi
INFO assistente.grafo revisore coerente=sì motivo=L'utente ha chiesto l'ora corrente a Tokyo e lo strumento fornito ha restituito questa informazione. -> fine
INFO assistente.agente citazioni verificate=- sconosciute=- ricerche=0 passaggi_ricevuti=0
```

## generica: «Ciao! Cosa sai fare?»

- Atteso: nessuno strumento → **atteso**
- Nessuno strumento chiamato

Risposta:

> Sono un assistente di laboratorio. Posso aiutarti con diverse attività basate sulle mie capacità e strumenti, come ad esempio:
> 
> *   Cercare informazioni in documenti specifici (come ricette).
> *   Eseguire calcoli matematici.
> *   Convertire unità di misura.
> *   Verificare la data e l'ora corrente o calcolare giorni.
> *   Consultare un inventario di materiali del laboratorio.
> *   Gestire note personali.
> 
> Come posso esserti utile oggi?

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La domanda è un saluto e una richiesta di informazioni sulle capacità dell'assistente, rientrando nell'ambito delle domande che proseguono la conversazione. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo revisore coerente=sì motivo=La risposta proposta risponde direttamente alla domanda dell'utente elencando le capacità dell'assistente in modo chiaro e strutturato. -> fine
INFO assistente.agente citazioni verificate=- sconosciute=- ricerche=0 passaggi_ricevuti=0
```

## senza_risposta: «Qual è la ricetta del tiramisù?»

- Atteso: ricerca chiamata, astensione, nessuna citazione → **atteso**
- Strumento `search_documents` {"query": "tiramisù"} → modalità base, passaggi: 575.1 (Brioches, 0.548), 560.0 (Presnitz, 0.528), 261.0 (Braciuola di manzo ripiena in umido, 0.526), 182.0 (Krapfen I, 0.525), 256.2 (Fricassea, 0.523)

Risposta:

> Non ho trovato la ricetta del tiramisù nei documenti disponibili.

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La richiesta riguarda una ricetta culinaria, rientrando nell'ambito delle conoscenze specifiche del libro di Pellegrino Artusi. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo strumento passaggio=1 nome=search_documents argomenti={'query': 'tiramisù'} risultato={"modalita":"base","query_usate":["tiramisù"],"passaggi":[{"id":"575.1","ricetta":575,"titolo":"Brioches","capitolo":"Pasticceria","posizione_chunk":1,"score":0.548,"testo":"lievitato disfatelo alquanto e con esso riempite a metà una ventina di stampini di latta rigati, che avanti avrete unti con burro liquido o lardo e spolverizzati con farina mista a zucchero a velo. Rimetteteli a lievitare, poi dorateli e cuoceteli al forno o al forno da campagna."},{"id":"560.0","ricetta":560,"titolo":"Presnitz","capitolo":"Pasticceria","posizione_chunk":0,"score":0.528,"testo":"Eccovi un altro dolce di tedescheria e come buono! Ne vidi uno che era fattura della prima pasticceria di Trieste, lo assaggiai e mi piacque. Chiestane la ricetta la misi alla prova e riuscì perfettamente; quindi, mentre ve lo descrivo, mi dichiaro gratissimo alla gentilezza di chi mi fece questo favore. Uva sultanina, grammi 160. Zucchero, grammi 130. Noci sgusciate, grammi 130. Focaccia rafferma, grammi 110. Mandorle dolci sbucciate, grammi 60. Pinoli, grammi 60. Cedro candito, grammi 35. Arancio candito, grammi 35. Spezie composte di cannella, garofani e macis, grammi 5. Sale, grammi 2. Cipro, decilitri 1. Rhum, decilitri 1. L'uva sultanina, dopo averla nettata, mettetela in infusione nel cipro e nel rum mescolati insieme; lasciatela così diverse ore e levatela quando comincia a gonfia…"},{"id":"261.0","ricetta":261,"titolo":"Braciuola di manzo ripiena in umido","capitolo":"Umidi","posizione_chunk":0,"score":0.526,"testo":"La braciuola di manzo ripiena arrosto del N. 537 potete cuocerla anche in umido col burro tirandola a cottura con acqua e sugo di pomodoro e servirla con un contorno qualunque."},{"id":"182.0","ricetta":182,"titolo":"Krapfen I","capitolo":"Fritti","posizione_chunk":0,"score":0.525,"testo":"Proviamoci di descrivere il piatto che porta questo nome di tedescheria ed andiamo pure in cerca del buono e del bello in qualunque luogo si trovino; ma per decoro di noi stessi e della patria nostra non imitiamo mai ciecamente le altre nazioni per solo spirito di stranieromania. Farina d'Ungheria, grammi 150. Burro, grammi 40. Lievito di birra, quanto una grossa noce. Uova, uno intero e un rosso. Zucchero, un cucchiaino. Sale, una buona presa."},{"id":"256.2","ricetta":256,"titolo":"Fricassea","capitolo":"Umidi","posizione_chunk":2,"score":0.523,"testo":"se no, un pizzico di funghi secchi. Quando siete per mandarla in tavola ritirate la cazzaruola dal fuoco e versateci a poco per volta, mescolando, i rossi d'uovo frullati coll'agro di limone. Se la fricassea fosse di pollo, tagliatelo a pezzi nelle giunture, escludendo la testa, il collo e le zampe; pel resto regolatevi nello stesso modo. La fricassea fatta in questa maniera è un piatto sano e delicato che piace specialmente a chi non ha il gusto viziato a sapori forti e piccanti."}],"nota":""}
INFO assistente.grafo agente: chiamata al modello con 4 messaggi
INFO assistente.grafo revisore coerente=sì motivo=La ricerca non ha prodotto risultati pertinenti per la ricetta del tiramisù nei documenti forniti. -> fine
INFO assistente.agente citazioni verificate=- sconosciute=- ricerche=1 passaggi_ricevuti=5
```

Log del server di ricerca:

```
2026-11-18 10:15:53,590 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi top_k_max=10
2026-11-18 10:16:05,613 INFO rag.server_mcp ricerca esito=ok modalita=base query="tiramisù" top_k=5 filtro=- passaggi=5 ids=575.1,560.0,261.0,182.0,256.2 nota="" ms=9166
```
