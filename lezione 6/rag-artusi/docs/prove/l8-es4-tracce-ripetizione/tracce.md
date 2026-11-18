# Lezione 8 · Es. 4 — tracce con le soglie

- Data: 2026-11-18 14:58 · modello `google/gemma-4-e2b` · variante strumenti `locale` · server MCP da `server_mcp.json`
- Comando (da `lezione 4/assistente-laboratorio`): `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.prove_rag --serie soglie --uscita <cartella>`

| Caso | Domanda | Atteso | Strumenti | Citazioni verificate / sconosciute | Esito | Durata |
|---|---|---|---|---|---|---|
| affidabile | Che vino si usa per il pollo alla cacciatora? | ricerca, passaggi affidabili, citazioni verificate, nessun «da verificare» | search_documents | 208.0 / - | **atteso** | 202.2 s |
| da_verificare | Perché gli gnocchi possono sciogliersi nell'acqua? | ricerca, passaggi di fascia media, risposta segnata «da verificare sulla fonte» | search_documents | 89.1 / - | **non atteso** | 168.5 s |

## affidabile: «Che vino si usa per il pollo alla cacciatora?»

- Atteso: ricerca, passaggi affidabili, citazioni verificate, nessun «da verificare» → **atteso**
- Strumento `search_documents` {"query": "pollo alla cacciatora vino"} → modalità base, passaggi: 208.0 (Pollo alla cacciatora, 0.768, affidabile), 539.0 (Pollo ripieno arrosto, 0.717, media), 258.1 (Pollo disossato ripieno, 0.715, media), 545.0 (Pollo vestito, 0.713, media), 268.0 (Pollo alla Marengo, 0.709, media)

Risposta:

> Per il pollo alla cacciatora, si consiglia di annaffiare con mezzo bicchiere di San Giovese o altro vino rosso del migliore, insieme a sugo di pomodoro [208.0].

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La domanda riguarda consigli culinari e abbinamenti di vino legati alla cucina. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo strumento passaggio=1 nome=search_documents argomenti={'query': 'pollo alla cacciatora vino'} risultato={"modalita":"base","query_usate":["pollo alla cacciatora vino"],"passaggi":[{"id":"208.0","ricetta":208,"titolo":"Pollo alla cacciatora","capitolo":"Fritti","posizione_chunk":0,"score":0.768,"fascia":"affidabile","testo":"Trinciate una grossa cipolla e tenetela per più di mezz'ora nell'acqua fresca, indi asciugatela e gettatela in padella con olio o lardo. Quando è cotta mettetela da parte. Spezzettate un pollastro, friggetelo nell'unto che resta e, rosolato che sia, uniteci la detta cipolla, conditelo con sale e pepe e annaffiatelo con mezzo bicchiere di San Giovese od altro vino rosso del migliore e alquanto sugo di pomodoro e, dopo cinque minuti di bollitura, servitelo. Vi avverto che non è piatto per gli stomachi deboli."},{"id":"539.0","ricetta":539,"titolo":"Pollo ripieno arrosto","capitolo":"Arrosti","posizione_chunk":0,"score":0.717,"fascia":"media","testo":"Non è un ripieno da cucina fine, ma da famiglia. Per un pollo di mediocre grandezza eccovi all'incirca la dose degli ingredienti: Due salsicce. Il fegatino, la cresta e i bargigli del pollo medesimo. Otto o dieci marroni bene arrostiti. Una pallina di tartufi o, in mancanza di questi, alcuni pezzetti di funghi secchi. L'odore di noce moscata. Un uovo. Se invece di un pollo fosse un tacchino, duplicate la dose. Cominciate col dare alle salsicce e alle rigaglie mezza cottura nel burro, bagnandole con un po' di brodo se occorre; conditele con poco sale e poco pepe a motivo delle salsicce. Levatele asciutte e nell'umido che resta gettate una midolla di pane, per ottenere con un po' di brodo due cucchiaiate di pappa soda. Spellate le salsicce, tritate con la lunetta le rigaglie e i funghi ramm…"},{"id":"258.1","ricetta":258,"titolo":"Pollo disossato ripieno","capitolo":"Umidi","posizione_chunk":1,"score":0.715,"fascia":"media","testo":"levatela tutta e levate la forcella del petto. Fatto questo, rovesciate le coscie e le ali, già spoglie d'ossa, ritirandole all'interno e portate via tutti i tendini che trovate framezzo alla carne. Ora che il pollo è disossato, se fosse alquanto grosso, formate il composto per riempirlo, con grammi 300 circa di magro di vitella di latte; se piccolo, regolatevi in proporzione. Tritatelo prima, poi pestatelo nel mortaio per ridurlo ben fine, e a questa carne aggiungete una grossa midolla di pane inzuppata nel brodo, un pugno di parmigiano grattato, tre rossi d'uovo, sale, pepe e, se vi piace, odore di noce moscata. Per ultimo mescolate nel composto, grammi 20 di prosciutto grasso e magro, e grammi 20 di lingua salata, tagliati l'uno e l'altra a piccoli dadi; riempito che abbiate il pollo c…"},{"id":"545.0","ricetta":545,"titolo":"Pollo vestito","capitolo":"Arrosti","posizione_chunk":0,"score":0.713,"fascia":"media","testo":"Non è piatto da farne gran caso, ma può recare sorpresa in un pranzo famigliare. Prendete il busto di un pollastro giovane, cioè privo delle zampe, del collo e delle interiora; ungetelo tutto con burro diaccio, spolverizzatelo di sale, e un pizzico di questo versatelo nell'interno. Poi, colle ali piegate, lasciatelo con due larghe e sottili fette di prosciutto più magro che grasso e copritelo con la pasta descritta nella ricetta N. 277, tirata col matterello alla grossezza di uno scudo all'incirca. Doratela col rosso d'uovo e cuocete il pollo così vestito a moderato calore nel forno o nel forno da campagna. Servitelo come sta per essere aperto e trinciato sulla tavola. A me sembra migliore diaccio che caldo."},{"id":"268.0","ricetta":268,"titolo":"Pollo alla Marengo","capitolo":"Umidi","posizione_chunk":0,"score":0.709,"fascia":"media","testo":"La sera della battaglia di Marengo, nel sottosopra di quella giornata non trovandosi i carri della cucina, il cuoco al primo Console e ai Generali improvvisò, con galline rubate, un piatto che manipolato all'incirca come quello che qui vi descrivo, fu chiamato Pollo alla Marengo; e si dice che esso fu poi sempre nelle grazie di Napoleone, se non pel merito suo, ma perchè gli rammentava quella gloriosa vittoria. Prendete un pollo giovane ed escludendone il collo e le zampe, tagliatelo a pezzi grossi nelle giunture. Mettetelo alla sautè con grammi 30 di burro, una cucchiaiata d'olio e conditelo con sale, pepe e una presa di noce moscata. Rosolati che sieno i pezzi da una parte e dall'altra scolate via l'unto e gettate nella sautè una cucchiaiata rasa di farina e un decilitro di vino bianco.…"}],"nota":""}
INFO assistente.grafo agente: chiamata al modello con 4 messaggi
INFO assistente.grafo revisore coerente=sì motivo=La risposta è basata sui risultati trovati nello strumento di ricerca riguardanti la ricetta del pollo alla cacciatora. -> fine
INFO assistente.agente citazioni verificate=208.0 sconosciute=- ricerche=1 passaggi_ricevuti=5
```

Log del server di ricerca:

```
2026-11-18 14:53:42,630 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi modalita=base soglie=0.73/0.7 top_k_max=10
2026-11-18 14:53:47,444 INFO rag.server_mcp ricerca esito=ok modalita=base query="pollo alla cacciatora vino" top_k=5 filtro=- passaggi=5 ids=208.0,539.0,258.1,545.0,268.0 nota="" ms=4448 query_usate=1 llm=0 ripieghi=- esclusi_soglia=0
```

## da_verificare: «Perché gli gnocchi possono sciogliersi nell'acqua?»

- Atteso: ricerca, passaggi di fascia media, risposta segnata «da verificare sulla fonte» → **non atteso** (la risposta non dice «da verificare»)
- Strumento `search_documents` {"query": "perché gli gnocchi possono sciogliersi nell'acqua"} → modalità base, passaggi: 89.1 (Gnocchi di patate, 0.713, media), 90.0 (Gnocchi di farina gialla, 0.711, media), 489.0 (Sparnocchie, 0.703, media) · nota: 2 passaggi esclusi perché sotto la soglia minima (0.70)

Risposta:

> Gli gnocchi si liquefanno nell'acqua perché erano stati intrisi con poca farina e appena furono nell'acqua bollente si liquefecero [89.1].

Log dell'agente:

```
INFO assistente.grafo riassunto: 1 messaggi, sotto la soglia di 20: nessuna chiamata
INFO assistente.grafo router categoria=conversazione motivo=La domanda riguarda la preparazione e le proprietà degli ingredienti culinari. -> agente
INFO assistente.grafo agente: chiamata al modello con 2 messaggi
INFO assistente.grafo strumento passaggio=1 nome=search_documents argomenti={'query': "perché gli gnocchi possono sciogliersi nell'acqua"} risultato={"modalita":"base","query_usate":["perché gli gnocchi possono sciogliersi nell'acqua"],"passaggi":[{"id":"89.1","ricetta":89,"titolo":"Gnocchi di patate","capitolo":"Minestre asciutte e di magro","posizione_chunk":1,"score":0.713,"fascia":"media","testo":"portati via. — Non inarchi le ciglia, signora — risposi io — chè lo strano fenomeno è naturale: quelli gnocchi erano stati intrisi con poca farina e appena furono nell'acqua bollente si liquefecero. — Cuocete le patate nell'acqua o, meglio, a vapore e, calde bollenti, spellatele e passatele per istaccio. Poi intridetele colla detta farina e lavorate alquanto l'impasto colle mani, tirandolo a cilindro sottile per poterlo tagliare a tocchetti lunghi tre centimetri circa. Spolverizzateli leggermente di farina e, prendendoli uno alla volta, scavateli col pollice sul rovescio di una grattugia. Metteteli a cuocere nell'acqua salata per dieci minuti, levateli asciutti e conditeli con cacio, burro e sugo di pomodoro, piacendovi. Se li volete più delicati cuoceteli nel latte e serviteli senza scol…"},{"id":"90.0","ricetta":90,"titolo":"Gnocchi di farina gialla","capitolo":"Minestre asciutte e di magro","posizione_chunk":0,"score":0.711,"fascia":"media","testo":"Quando vi sentite una certa ripienezza prodotta da esuberanza di nutrizione, se ricorrete a una minestra di questi gnocchi potrete, per la loro leggerezza e poca sostanza, neutralizzarla; e più ancora se farete seguire ad essa un piatto di pesce di facile digestione. La farina, per quest'uso, è bene sia macinata grossa; se no è meglio ricorrere al semolino fine di granturco, che ora trovasi in commercio. Salate l'acqua e, quando bolle, versate colla mano sinistra la farina un po' per volta e col mestolo nella destra, mescolate continuamente. È necessario che questa farina bolla molto, e quando essa è ristretta in modo da reggere bene sul mestolo, gettatela, con un coltello da tavola, a tocchetti entro a un vassoio e ad ogni strato conditela con cacio, burro, sugo di pomodoro o conserva sc…"},{"id":"489.0","ricetta":489,"titolo":"Sparnocchie","capitolo":"Piatti di pesce","posizione_chunk":0,"score":0.703,"fascia":"media","testo":"Le cicale mi rammentano le sparnocchie che, a prima vista, le rassomigliano; ma esaminato bene questo crostaceo ha la forma di un grosso gambero di mare del peso comunemente di 50 o 60 grammi. È di sapore più delicato dell'arigusta e, come questa, si usa mangiarlo lesso; ma perchè non perda sapore meglio è di arrostirlo in gratella, senza condimento alcuno, e dopo sgusciarlo e condirlo con olio, pepe, sale ed agro di limone. Le sparnocchie piccole si possono anche, come i gamberi, infarinare e friggerle così naturali, oppure nel modo indicato per le cicale."}],"nota":"2 passaggi esclusi perché sotto la soglia minima (0.70)"}
INFO assistente.grafo agente: chiamata al modello con 4 messaggi
INFO assistente.grafo revisore coerente=sì motivo=La risposta è coerente poiché estrae direttamente la spiegazione fornita dal documento recuperato riguardo alla liquefazione degli gnocchi. -> fine
INFO assistente.agente citazioni verificate=89.1 sconosciute=- ricerche=1 passaggi_ricevuti=3
```

Log del server di ricerca:

```
2026-11-18 14:57:01,656 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi modalita=base soglie=0.73/0.7 top_k_max=10
2026-11-18 14:57:06,635 INFO rag.server_mcp ricerca esito=ok modalita=base query="perché gli gnocchi possono sciogliersi nell'acqua" top_k=5 filtro=- passaggi=3 ids=89.1,90.0,489.0 nota="2 passaggi esclusi perché sotto la soglia minima (0.70)" ms=4681 query_usate=1 llm=0 ripieghi=- esclusi_soglia=2
```
