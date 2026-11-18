# Lezione 8 · Es. 4 — tracce con le soglie

- Data: 2026-11-18 14:51 · modello `google/gemma-4-e2b` · variante strumenti `locale` · server MCP da `server_mcp.json`
- Comando (da `lezione 4/assistente-laboratorio`): `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.prove_rag --serie soglie --uscita <cartella>`

| Caso | Domanda | Atteso | Strumenti | Citazioni verificate / sconosciute | Esito | Durata |
|---|---|---|---|---|---|---|
| affidabile | Che vino si usa per il pollo alla cacciatora? | ricerca, passaggi affidabili, citazioni verificate, nessun «da verificare» | search_documents | - / - | **non atteso** | 212.6 s |
| da_verificare | Perché gli gnocchi possono sciogliersi nell'acqua? | ricerca, passaggi di fascia media, risposta segnata «da verificare sulla fonte» | search_documents | 89.1 / - | **non atteso** | 200.4 s |
| senza_risposta_soglie | Qual è la ricetta del tiramisù? | ricerca con lista vuota (sotto la soglia), astensione, nessuna citazione | search_documents | - / - | **atteso** | 181.9 s |

## affidabile: «Che vino si usa per il pollo alla cacciatora?»

- Atteso: ricerca, passaggi affidabili, citazioni verificate, nessun «da verificare» → **non atteso** (nessuna citazione verificata)
- Strumento `search_documents` {"query": "vino per pollo alla cacciatora"} → modalità base, passaggi: 208.0 (Pollo alla cacciatora, 0.764, affidabile), 539.0 (Pollo ripieno arrosto, 0.704, media), 727.1 (Marena, 0.702, media), 545.0 (Pollo vestito, 0.701, media) · nota: 1 passaggio escluso perché sotto la soglia minima (0.70)

Risposta:

> Si può usare mezzo bicchiere di San Giovese o altro vino rosso del migliore.

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La domanda riguarda consigli culinari e ricette che rientrano nell'ambito del libro di Pellegrino Artusi. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo strumento passaggio=1 nome=search_documents argomenti={'query': 'vino per pollo alla cacciatora'} risultato={"modalita":"base","query_usate":["vino per pollo alla cacciatora"],"passaggi":[{"id":"208.0","ricetta":208,"titolo":"Pollo alla cacciatora","capitolo":"Fritti","posizione_chunk":0,"score":0.764,"fascia":"affidabile","testo":"Trinciate una grossa cipolla e tenetela per più di mezz'ora nell'acqua fresca, indi asciugatela e gettatela in padella con olio o lardo. Quando è cotta mettetela da parte. Spezzettate un pollastro, friggetelo nell'unto che resta e, rosolato che sia, uniteci la detta cipolla, conditelo con sale e pepe e annaffiatelo con mezzo bicchiere di San Giovese od altro vino rosso del migliore e alquanto sugo di pomodoro e, dopo cinque minuti di bollitura, servitelo. Vi avverto che non è piatto per gli stomachi deboli."},{"id":"539.0","ricetta":539,"titolo":"Pollo ripieno arrosto","capitolo":"Arrosti","posizione_chunk":0,"score":0.704,"fascia":"media","testo":"Non è un ripieno da cucina fine, ma da famiglia. Per un pollo di mediocre grandezza eccovi all'incirca la dose degli ingredienti: Due salsicce. Il fegatino, la cresta e i bargigli del pollo medesimo. Otto o dieci marroni bene arrostiti. Una pallina di tartufi o, in mancanza di questi, alcuni pezzetti di funghi secchi. L'odore di noce moscata. Un uovo. Se invece di un pollo fosse un tacchino, duplicate la dose. Cominciate col dare alle salsicce e alle rigaglie mezza cottura nel burro, bagnandole con un po' di brodo se occorre; conditele con poco sale e poco pepe a motivo delle salsicce. Levatele asciutte e nell'umido che resta gettate una midolla di pane, per ottenere con un po' di brodo due cucchiaiate di pappa soda. Spellate le salsicce, tritate con la lunetta le rigaglie e i funghi ramm…"},{"id":"727.1","ricetta":727,"titolo":"Marena","capitolo":"Siroppi","posizione_chunk":1,"score":0.702,"fascia":"media","testo":"depurato, mettetelo al fuoco nelle seguenti proporzioni e col rammentato pezzo di cannella. Sugo depurato, chilogrammi 6. Zucchero bianchissimo in polvere, chilogrammi 8. Acido citrico, grammi 50. Per versare lo zucchero e l'acido citrico aspettate che il liquido sia ben caldo e poi mescolate spesso onde lo zucchero non si depositi in fondo e non prenda di bruciato. La bollitura dev'esser breve; quattro o cinque minuti sono bastanti a incorporare lo zucchero nel liquido. Una bollitura prolungata farebbe perdere l'aroma al frutto, mentre che una insufficiente produrrebbe col tempo la deposizione dello zucchero. Quando levate la marena dal fuoco, versatela in vaso di terra e imbottigliatela diaccia. Tappate le bottiglie con sughero senza catrame e conservatele in cantina dove tanto la maren…"},{"id":"545.0","ricetta":545,"titolo":"Pollo vestito","capitolo":"Arrosti","posizione_chunk":0,"score":0.701,"fascia":"media","testo":"Non è piatto da farne gran caso, ma può recare sorpresa in un pranzo famigliare. Prendete il busto di un pollastro giovane, cioè privo delle zampe, del collo e delle interiora; ungetelo tutto con burro diaccio, spolverizzatelo di sale, e un pizzico di questo versatelo nell'interno. Poi, colle ali piegate, lasciatelo con due larghe e sottili fette di prosciutto più magro che grasso e copritelo con la pasta descritta nella ricetta N. 277, tirata col matterello alla grossezza di uno scudo all'incirca. Doratela col rosso d'uovo e cuocete il pollo così vestito a moderato calore nel forno o nel forno da campagna. Servitelo come sta per essere aperto e trinciato sulla tavola. A me sembra migliore diaccio che caldo."}],"nota":"1 passaggio escluso perché sotto la soglia minima (0.70)"}
INFO assistente.grafo agente: chiamata al modello con 4 messaggi
INFO assistente.grafo revisore coerente=sì motivo=La risposta proposta è coerente con la ricerca effettuata, fornendo un suggerimento di vino. -> fine
INFO assistente.agente citazioni verificate=- sconosciute=- ricerche=1 passaggi_ricevuti=4
```

Log del server di ricerca:

```
2026-11-18 14:43:31,328 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi modalita=base soglie=0.73/0.7 top_k_max=10
2026-11-18 14:43:36,198 INFO rag.server_mcp ricerca esito=ok modalita=base query="vino per pollo alla cacciatora" top_k=5 filtro=- passaggi=4 ids=208.0,539.0,727.1,545.0 nota="1 passaggio escluso perché sotto la soglia minima (0.70)" ms=4553 query_usate=1 llm=0 ripieghi=- esclusi_soglia=1
```

## da_verificare: «Perché gli gnocchi possono sciogliersi nell'acqua?»

- Atteso: ricerca, passaggi di fascia media, risposta segnata «da verificare sulla fonte» → **non atteso** (la risposta non dice «da verificare»)
- Strumento `search_documents` {"query": "perché gli gnocchi si sciolgono nell'acqua"} → modalità base, passaggi: 89.1 (Gnocchi di patate, 0.725, media), 89.0 (Gnocchi di patate, 0.711, media), 230.0 (Gnocchi di semolino, 0.706, media), 470.1 (Triglie di scoglio in gratella, 0.705, media), 90.0 (Gnocchi di farina gialla, 0.704, media)

Risposta:

> Gli gnocchi si liquefanno nell'acqua perché erano stati intrisi con poca farina e appena furono nell'acqua bollente, si liquefecero [89.1].

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La domanda riguarda la preparazione e le proprietà degli ingredienti culinari. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo strumento passaggio=1 nome=search_documents argomenti={'query': "perché gli gnocchi si sciolgono nell'acqua"} risultato={"modalita":"base","query_usate":["perché gli gnocchi si sciolgono nell'acqua"],"passaggi":[{"id":"89.1","ricetta":89,"titolo":"Gnocchi di patate","capitolo":"Minestre asciutte e di magro","posizione_chunk":1,"score":0.725,"fascia":"media","testo":"portati via. — Non inarchi le ciglia, signora — risposi io — chè lo strano fenomeno è naturale: quelli gnocchi erano stati intrisi con poca farina e appena furono nell'acqua bollente si liquefecero. — Cuocete le patate nell'acqua o, meglio, a vapore e, calde bollenti, spellatele e passatele per istaccio. Poi intridetele colla detta farina e lavorate alquanto l'impasto colle mani, tirandolo a cilindro sottile per poterlo tagliare a tocchetti lunghi tre centimetri circa. Spolverizzateli leggermente di farina e, prendendoli uno alla volta, scavateli col pollice sul rovescio di una grattugia. Metteteli a cuocere nell'acqua salata per dieci minuti, levateli asciutti e conditeli con cacio, burro e sugo di pomodoro, piacendovi. Se li volete più delicati cuoceteli nel latte e serviteli senza scol…"},{"id":"89.0","ricetta":89,"titolo":"Gnocchi di patate","capitolo":"Minestre asciutte e di magro","posizione_chunk":0,"score":0.711,"fascia":"media","testo":"La famiglia de' gnocchi è numerosa. Vi ho già descritto gli gnocchi in brodo del N. 14: ora v'indicherò gli gnocchi di patate e di farina gialla per minestra e più avanti quelli di semolino e alla romana per tramesso o per contorno, e quelli di latte per dolce. Patate grosse e gialle, grammi 400. Farina di grano, grammi 150. Vi noto la proporzione della farina per intriderli, onde non avesse ad accadervi come ad una signora che, me presente, appena affondato il mestolo per muoverli nella pentola non trovò più nulla; gli gnocchi erano spariti. — O dov'erano andati? — mi domandò con premurosa curiosità un'altra signora, a cui per ridere raccontai il fatto, credendo forse che il folletto li avesse portati via. — Non inarchi le ciglia, signora — risposi io — chè lo strano fenomeno è naturale:…"},{"id":"230.0","ricetta":230,"titolo":"Gnocchi di semolino","capitolo":"Tramessi","posizione_chunk":0,"score":0.706,"fascia":"media","testo":"Latte, decilitri 4. Semolino, grammi 120. Burro, grammi 50. Parmigiano grattato, grammi 40. Uova, N. 2. Sale, quanto basta. Cuocete il semolino nel latte e quando siete per ritirarlo dal fuoco salatelo e versatevi metà del burro e metà del parmigiano. Poi, quando è ancora ben caldo, aggiungete le uova e mescolate, indi versatelo sulla spianatoia, o sopra un vassoio, distendetelo alla grossezza di un dito e mezzo e lasciate che diacci per tagliarlo a mandorle. Eccovi gli gnocchi che collocherete uno sopra l'altro in bella mostra entro un vassoio proporzionato, intramezzandoli col resto del burro a pezzetti e spolverizzandoli, suolo per suolo, ma non alla superficie, col resto del parmigiano. Per ultimo, rosolateli al forno da campagna e serviteli caldi o soli o per contorno ad un piatto di…"},{"id":"470.1","ricetta":470,"titolo":"Triglie di scoglio in gratella","capitolo":"Piatti di pesce","posizione_chunk":1,"score":0.705,"fascia":"media","testo":"servo che aveva rotto disavvedutamente un bicchiere di cristallo. Augusto, ai cui piedi cadde lo schiavo, invocando la sua intercessione, potè salvarlo a stento con un ingegnoso suo strattagemma. Le triglie grosse di scoglio, che raggiungevano il peso non mica di soli grammi 500 a 600, come dico più sopra, ma perfino di 4 a 6 libbre, erano stimate assai e pagate a prezzi altissimi, favolosi. La mollezza dei costumi e la golosità avendo nei Romani raffinato il senso del gusto, studiavansi di appagarlo con le vivande più delicate e perciò avevano inventata una certa salsa chiamata gareleo nella quale disfacevano e stemperavano la coratella di questo grosso pesce per intingervi la carne del medesimo."},{"id":"90.0","ricetta":90,"titolo":"Gnocchi di farina gialla","capitolo":"Minestre asciutte e di magro","posizione_chunk":0,"score":0.704,"fascia":"media","testo":"Quando vi sentite una certa ripienezza prodotta da esuberanza di nutrizione, se ricorrete a una minestra di questi gnocchi potrete, per la loro leggerezza e poca sostanza, neutralizzarla; e più ancora se farete seguire ad essa un piatto di pesce di facile digestione. La farina, per quest'uso, è bene sia macinata grossa; se no è meglio ricorrere al semolino fine di granturco, che ora trovasi in commercio. Salate l'acqua e, quando bolle, versate colla mano sinistra la farina un po' per volta e col mestolo nella destra, mescolate continuamente. È necessario che questa farina bolla molto, e quando essa è ristretta in modo da reggere bene sul mestolo, gettatela, con un coltello da tavola, a tocchetti entro a un vassoio e ad ogni strato conditela con cacio, burro, sugo di pomodoro o conserva sc…"}],"nota":""}
INFO assistente.grafo agente: chiamata al modello con 4 messaggi
INFO assistente.grafo revisore coerente=sì motivo=La risposta proposta è coerente con il testo recuperato e risponde alla domanda in modo sintetico. -> fine
INFO assistente.agente citazioni verificate=89.1 sconosciute=- ricerche=1 passaggi_ricevuti=5
```

Log del server di ricerca:

```
2026-11-18 14:46:37,734 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi modalita=base soglie=0.73/0.7 top_k_max=10
2026-11-18 14:46:42,886 INFO rag.server_mcp ricerca esito=ok modalita=base query="perché gli gnocchi si sciolgono nell'acqua" top_k=5 filtro=- passaggi=5 ids=89.1,89.0,230.0,470.1,90.0 nota="" ms=4687 query_usate=1 llm=0 ripieghi=- esclusi_soglia=0
```

## senza_risposta_soglie: «Qual è la ricetta del tiramisù?»

- Atteso: ricerca con lista vuota (sotto la soglia), astensione, nessuna citazione → **atteso**
- Strumento `search_documents` {"query": "tiramisù"} → modalità base, passaggi: nessuno · nota: nessun passaggio sopra la soglia minima (0.70): il libro non sembra contenere la risposta

Risposta:

> Nel libro non ho trovato la ricetta del tiramisù.

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La richiesta riguarda una ricetta, rientrando nell'ambito delle richieste culinarie specifiche menzionate. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo strumento passaggio=1 nome=search_documents argomenti={'query': 'tiramisù'} risultato={"modalita":"base","query_usate":["tiramisù"],"passaggi":[],"nota":"nessun passaggio sopra la soglia minima (0.70): il libro non sembra contenere la risposta"}
INFO assistente.grafo agente: chiamata al modello con 4 messaggi
INFO assistente.grafo revisore coerente=sì motivo=La ricerca tramite strumento non ha trovato la ricetta del tiramisù nel documento consultato. -> fine
INFO assistente.agente citazioni verificate=- sconosciute=- ricerche=1 passaggi_ricevuti=0
```

Log del server di ricerca:

```
2026-11-18 14:49:48,976 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi modalita=base soglie=0.73/0.7 top_k_max=10
2026-11-18 14:49:53,635 INFO rag.server_mcp ricerca esito=ok modalita=base query="tiramisù" top_k=5 filtro=- passaggi=0 ids=- nota="nessun passaggio sopra la soglia minima (0.70): il libro non sembra contenere la risposta" ms=4309 query_usate=1 llm=0 ripieghi=- esclusi_soglia=5
```
