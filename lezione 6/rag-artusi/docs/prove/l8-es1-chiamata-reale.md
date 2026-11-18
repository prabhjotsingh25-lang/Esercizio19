# Lezione 8 · Es. 1 — chiamata reale al server di ricerca (stdio)

- Data: 2026-11-18 · Qdrant (docker compose, collezione `artusi`) e LM Studio accesi
- Modello di embedding: `text-embedding-nomic-embed-text-v1.5@q8_0` · codice al commit `5de171d` + cliente stdio
- Comando: `.\.venv\Scripts\python.exe -m rag.cliente_mcp "domanda" [--top-k N] [--filtro CAPITOLO]`
  (avvia `python -m rag.server_mcp` via stdio, come farà l'agente). Righe di log del server da stderr.
- Nota: `ms` nel log è la durata della ricerca; la prima chiamata di una sessione di LM Studio è più lenta (carica il modello di embedding).

## `rag.cliente_mcp "Quanta farina serve per 400 grammi di patate negli gnocchi?" --top-k 3`

```
strumenti: search_documents
argomenti: {"query": "Quanta farina serve per 400 grammi di patate negli gnocchi?", "top_k": 3}
esito: ok
{
  "modalita": "base",
  "query_usate": [
    "Quanta farina serve per 400 grammi di patate negli gnocchi?"
  ],
  "passaggi": [
    {
      "id": "89.0",
      "ricetta": 89,
      "titolo": "Gnocchi di patate",
      "capitolo": "Minestre asciutte e di magro",
      "posizione_chunk": 0,
      "score": 0.773,
      "testo": "La famiglia de' gnocchi è numerosa. Vi ho già descritto gli gnocchi in brodo del N. 14: ora v'indicherò gli gnocchi di patate e di farina gialla per minestra e più avanti quelli di semolino e alla romana per tramesso o per contorno, e quelli di latte per dolce. Patate grosse e gialle, grammi 400. Farina di grano, grammi 150. Vi noto la proporzione della farina per intriderli, onde non avesse ad accadervi come ad una signora che, me presente, appena affondato il mestolo per muoverli nella pentola non trovò più nulla; gli gnocchi erano spariti. — O dov'erano andati? — mi domandò con premurosa curiosità un'altra signora, a cui per ridere raccontai il fatto, credendo forse che il folletto li avesse portati via. — Non inarchi le ciglia, signora — risposi io — chè lo strano fenomeno è naturale:…"
    },
    {
      "id": "90.0",
      "ricetta": 90,
      "titolo": "Gnocchi di farina gialla",
      "capitolo": "Minestre asciutte e di magro",
      "posizione_chunk": 0,
      "score": 0.748,
      "testo": "Quando vi sentite una certa ripienezza prodotta da esuberanza di nutrizione, se ricorrete a una minestra di questi gnocchi potrete, per la loro leggerezza e poca sostanza, neutralizzarla; e più ancora se farete seguire ad essa un piatto di pesce di facile digestione. La farina, per quest'uso, è bene sia macinata grossa; se no è meglio ricorrere al semolino fine di granturco, che ora trovasi in commercio. Salate l'acqua e, quando bolle, versate colla mano sinistra la farina un po' per volta e col mestolo nella destra, mescolate continuamente. È necessario che questa farina bolla molto, e quando essa è ristretta in modo da reggere bene sul mestolo, gettatela, con un coltello da tavola, a tocchetti entro a un vassoio e ad ogni strato conditela con cacio, burro, sugo di pomodoro o conserva sc…"
    },
    {
      "id": "14.0",
      "ricetta": 14,
      "titolo": "Gnocchi",
      "capitolo": "Minestre in brodo",
      "posizione_chunk": 0,
      "score": 0.745,
      "testo": "È una minestra da farsene onore; ma se non volete consumare appositamente per lei un petto di pollastra o di cappone, aspettate che vi capiti d'occasione. Cuocete nell'acqua, o meglio a vapore, grammi 200 di patate grosse e farinacee e passatele per istaccio. A queste unite il petto di pollo lesso tritato finissimo colla lunetta, grammi 40 di parmigiano grattato, due rossi d'uovo, sale quanto basta e odore di noce moscata. Mescolate e versate il composto sulla spianatoia sopra a grammi 30 o 40 (che tanti devono bastare) di farina per legarlo, e poterlo tirare a bastoncini grossi quanto il dito mignolo. Tagliate questi a tocchetti e gettateli nel brodo bollente ove una cottura di cinque o sei minuti sarà sufficiente. Questa dose potrà bastare per sette od otto persone. Se il petto di pollo…"
    }
  ],
  "nota": ""
}
(exit 0)
```

Log del server:

```
2026-11-18 09:54:41,224 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi top_k_max=10
2026-11-18 09:54:43,956 INFO rag.server_mcp ricerca esito=ok modalita=base query="Quanta farina serve per 400 grammi di patate negli gnocchi?" top_k=3 filtro=- passaggi=3 ids=89.0,90.0,14.0 nota="" ms=2308
```

## `rag.cliente_mcp "Che vino si usa per il pollo alla cacciatora?" --top-k 2 --filtro fritti`

```
strumenti: search_documents
argomenti: {"query": "Che vino si usa per il pollo alla cacciatora?", "top_k": 2, "filtro": "fritti"}
esito: ok
{
  "modalita": "base",
  "query_usate": [
    "Che vino si usa per il pollo alla cacciatora?"
  ],
  "passaggi": [
    {
      "id": "208.0",
      "ricetta": 208,
      "titolo": "Pollo alla cacciatora",
      "capitolo": "Fritti",
      "posizione_chunk": 0,
      "score": 0.749,
      "testo": "Trinciate una grossa cipolla e tenetela per più di mezz'ora nell'acqua fresca, indi asciugatela e gettatela in padella con olio o lardo. Quando è cotta mettetela da parte. Spezzettate un pollastro, friggetelo nell'unto che resta e, rosolato che sia, uniteci la detta cipolla, conditelo con sale e pepe e annaffiatelo con mezzo bicchiere di San Giovese od altro vino rosso del migliore e alquanto sugo di pomodoro e, dopo cinque minuti di bollitura, servitelo. Vi avverto che non è piatto per gli stomachi deboli."
    },
    {
      "id": "209.0",
      "ricetta": 209,
      "titolo": "Pollo fritto coi pomodori",
      "capitolo": "Fritti",
      "posizione_chunk": 0,
      "score": 0.701,
      "testo": "Ogni popolo usa per friggere quell'unto che si produce migliore nel proprio paese. In Toscana si dà la preferenza all'olio, in Lombardia al burro, e nell'Emilia al lardo che vi si prepara eccellente, cioè bianchissimo, sodo e con un odorino di alloro che consola annusandolo. Da ciò la strage inaudita, in quella regione, di giovani pollastri fritti nel lardo, coi pomodori. Nelle fritture di grasso io preferisco il lardo perchè mi sembra dia un gusto più grato e più saporito dell'olio. Il pollo si taglia a piccoli pezzi, si mette in padella così naturale con sufficiente quantità di lardo, condendolo con sale e pepe. Quando è cotto si scola dall'unto superfluo e vi si gettano i pomodori a pezzetti dopo averne tolti i semi. Si rimesta continuamente finchè i pomodori siensi quasi strutti e si…"
    }
  ],
  "nota": ""
}
(exit 0)
```

Log del server:

```
2026-11-18 09:54:55,081 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi top_k_max=10
2026-11-18 09:54:59,199 INFO rag.server_mcp ricerca esito=ok modalita=base query="Che vino si usa per il pollo alla cacciatora?" top_k=2 filtro=fritti passaggi=2 ids=208.0,209.0 nota="" ms=2321
```

## `rag.cliente_mcp "Qual è la ricetta del tiramisù?" --top-k 2`

```
strumenti: search_documents
argomenti: {"query": "Qual è la ricetta del tiramisù?", "top_k": 2}
esito: ok
{
  "modalita": "base",
  "query_usate": [
    "Qual è la ricetta del tiramisù?"
  ],
  "passaggi": [
    {
      "id": "372.3",
      "ricetta": 372,
      "titolo": "Pasticcio di lepre",
      "capitolo": "Rifreddi",
      "posizione_chunk": 3,
      "score": 0.706,
      "testo": "col resto della marsala e con brodo e passatela; poi pestate le ossa e procurate che passi di queste tutto quel che più potete, avvertendovi però occorrervi a quest'uopo uno staccio di fil di ferro. Ora, fate una balsamella con grammi 30 del detto burro, la farina e il latte indicati e, cotta che sia, versate nella stessa cazzaruola tutta la carne passata, tanto quella della lepre che della vitella di latte cruda, aggiungete le due uova, mescolate bene ed assaggiate il composto se è dosato giusto di condimenti, per aggiungere, se occorre, sale e il resto del burro. Adesso incassate il pasticcio colla pasta qui sotto descritta e per riempirlo regolatevi come nel N. 370. I tartufi tagliateli a tocchetti grossi come le nocciuole e così crudi e con tutti i filetti descritti disponeteli a tre…"
    },
    {
      "id": "609.0",
      "ricetta": 609,
      "titolo": "Pizza alla napoletana",
      "capitolo": "Pasticceria",
      "posizione_chunk": 0,
      "score": 0.704,
      "testo": "Pasta frolla metà della ricetta A del N. 589, oppure l'intera ricetta B dello stesso numero. Ricotta, grammi 150. Mandorle dolci con tre amare, grammi 70. Zucchero, grammi 50. Farina, grammi 20 Uova, N. 1 e un rosso. Odore di scorza di limone o di vainiglia. Latte, mezzo bicchiere. Fate una crema col latte, collo zucchero, colla farina, con l'uovo intero sopraindicato e quando è cotta ed ancor bollente aggiungete il rosso e datele l'odore. Unite quindi alla crema la ricotta e le mandorle sbucciate e pestate fini. Mescolate il tutto e riempite con questo composto la pasta frolla disposta a guisa di torta, e cioè fra due sfoglie della medesima ornata di sopra e dorata col rosso d'uovo. S'intende già che dev'essere cotta in forno, servita fredda e spolverizzata di zucchero a velo. A me sembr…"
    }
  ],
  "nota": ""
}
(exit 0)
```

Log del server:

```
2026-11-18 09:55:09,766 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi top_k_max=10
2026-11-18 09:55:13,263 INFO rag.server_mcp ricerca esito=ok modalita=base query="Qual è la ricetta del tiramisù?" top_k=2 filtro=- passaggi=2 ids=372.3,609.0 nota="" ms=2363
```

## `rag.cliente_mcp "gnocchi" --top-k 50`

```
strumenti: search_documents
argomenti: {"query": "gnocchi", "top_k": 50}
esito: ok
{
  "modalita": "base",
  "query_usate": [
    "gnocchi"
  ],
  "passaggi": [
    {
      "id": "89.0",
      "ricetta": 89,
      "titolo": "Gnocchi di patate",
      "capitolo": "Minestre asciutte e di magro",
      "posizione_chunk": 0,
      "score": 0.715,
      "testo": "La famiglia de' gnocchi è numerosa. Vi ho già descritto gli gnocchi in brodo del N. 14: ora v'indicherò gli gnocchi di patate e di farina gialla per minestra e più avanti quelli di semolino e alla romana per tramesso o per contorno, e quelli di latte per dolce. Patate grosse e gialle, grammi 400. Farina di grano, grammi 150. Vi noto la proporzione della farina per intriderli, onde non avesse ad accadervi come ad una signora che, me presente, appena affondato il mestolo per muoverli nella pentola non trovò più nulla; gli gnocchi erano spariti. — O dov'erano andati? — mi domandò con premurosa curiosità un'altra signora, a cui per ridere raccontai il fatto, credendo forse che il folletto li avesse portati via. — Non inarchi le ciglia, signora — risposi io — chè lo strano fenomeno è naturale:…"
    },
    {
      "id": "230.0",
      "ricetta": 230,
      "titolo": "Gnocchi di semolino",
      "capitolo": "Tramessi",
      "posizione_chunk": 0,
      "score": 0.683,
      "testo": "Latte, decilitri 4. Semolino, grammi 120. Burro, grammi 50. Parmigiano grattato, grammi 40. Uova, N. 2. Sale, quanto basta. Cuocete il semolino nel latte e quando siete per ritirarlo dal fuoco salatelo e versatevi metà del burro e metà del parmigiano. Poi, quando è ancora ben caldo, aggiungete le uova e mescolate, indi versatelo sulla spianatoia, o sopra un vassoio, distendetelo alla grossezza di un dito e mezzo e lasciate che diacci per tagliarlo a mandorle. Eccovi gli gnocchi che collocherete uno sopra l'altro in bella mostra entro un vassoio proporzionato, intramezzandoli col resto del burro a pezzetti e spolverizzandoli, suolo per suolo, ma non alla superficie, col resto del parmigiano. Per ultimo, rosolateli al forno da campagna e serviteli caldi o soli o per contorno ad un piatto di…"
    },
    {
      "id": "89.1",
      "ricetta": 89,
      "titolo": "Gnocchi di patate",
      "capitolo": "Minestre asciutte e di magro",
      "posizione_chunk": 1,
      "score": 0.678,
      "testo": "portati via. — Non inarchi le ciglia, signora — risposi io — chè lo strano fenomeno è naturale: quelli gnocchi erano stati intrisi con poca farina e appena furono nell'acqua bollente si liquefecero. — Cuocete le patate nell'acqua o, meglio, a vapore e, calde bollenti, spellatele e passatele per istaccio. Poi intridetele colla detta farina e lavorate alquanto l'impasto colle mani, tirandolo a cilindro sottile per poterlo tagliare a tocchetti lunghi tre centimetri circa. Spolverizzateli leggermente di farina e, prendendoli uno alla volta, scavateli col pollice sul rovescio di una grattugia. Metteteli a cuocere nell'acqua salata per dieci minuti, levateli asciutti e conditeli con cacio, burro e sugo di pomodoro, piacendovi. Se li volete più delicati cuoceteli nel latte e serviteli senza scol…"
    },
    {
      "id": "231.0",
      "ricetta": 231,
      "titolo": "Gnocchi alla romana",
      "capitolo": "Tramessi",
      "posizione_chunk": 0,
      "score": 0.663,
      "testo": "Questi gnocchi, che io ho modificato e dosati nella seguente maniera, spero vi piaceranno come sono piaciuti a quelli cui li ho imbanditi. Se ciò avviene fate un brindisi alla mia salute se sarò vivo, o mandatemi un requiescat se sarò andato a rincalzare i cavoli. Farina, grammi 150. Burro, grammi 50. Cacio gruiera, grammi 40. Parmigiano, grammi 20. Latte, mezzo litro. Uova, N. 2. Si dice che a tavola non si dovrebbe essere in meno del numero delle Grazie, nè in più del numero delle Muse. Se vi aggirate intorno al numero delle Muse, raddoppiate la dose."
    },
    {
      "id": "90.0",
      "ricetta": 90,
      "titolo": "Gnocchi di farina gialla",
      "capitolo": "Minestre asciutte e di magro",
      "posizione_chunk": 0,
      "score": 0.659,
      "testo": "Quando vi sentite una certa ripienezza prodotta da esuberanza di nutrizione, se ricorrete a una minestra di questi gnocchi potrete, per la loro leggerezza e poca sostanza, neutralizzarla; e più ancora se farete seguire ad essa un piatto di pesce di facile digestione. La farina, per quest'uso, è bene sia macinata grossa; se no è meglio ricorrere al semolino fine di granturco, che ora trovasi in commercio. Salate l'acqua e, quando bolle, versate colla mano sinistra la farina un po' per volta e col mestolo nella destra, mescolate continuamente. È necessario che questa farina bolla molto, e quando essa è ristretta in modo da reggere bene sul mestolo, gettatela, con un coltello da tavola, a tocchetti entro a un vassoio e ad ogni strato conditela con cacio, burro, sugo di pomodoro o conserva sc…"
    },
    {
      "id": "231.1",
      "ricetta": 231,
      "titolo": "Gnocchi alla romana",
      "capitolo": "Tramessi",
      "posizione_chunk": 1,
      "score": 0.642,
      "testo": "litro. Uova, N. 2. Si dice che a tavola non si dovrebbe essere in meno del numero delle Grazie, nè in più del numero delle Muse. Se vi aggirate intorno al numero delle Muse, raddoppiate la dose. Intridete la farina colle uova e col latte versato a poco per volta entro una cazzaruola, aggiungete il cacio gruiera a pezzettini e mettete l'intriso al fuoco mescolando continuamente. Quando sarà assodato per la cottura della farina, salatelo e aggiungete la metà del detto burro. Lasciate che il composto diacci e poi, nella stessa guisa degli gnocchi di farina gialla, mettetelo a tocchetti in un vassoio che regga al fuoco e conditeli via via col resto del burro a pezzetti e col parmigiano suddetto grattato; ma non alla superficie, perchè il parmigiano col fuoco sopra prende l'amaro. Rosolateli s…"
    },
    {
      "id": "699.0",
      "ricetta": 699,
      "titolo": "Gnocchi di latte",
      "capitolo": "Torte e dolci al cucchiaio",
      "posizione_chunk": 0,
      "score": 0.634,
      "testo": "Dose per sei persone. Latte, un litro. Zucchero, grammi 240. Amido ridotto in polvere, grammi 120. Rossi d'uovo, N. 8. Odore di vainiglia. Mescolate il tutto nel modo stesso che fareste per una crema e mettetelo al fuoco in una cazzaruola, girando continuamente il mestolo. Quando il composto sarà divenuto sodo, tenetelo ancora qualche minuto al fuoco e poi versatelo in una teglia o in un piatto all'altezza di un dito e mezzo e tagliatelo a mandorle quando sarà diacciato. Disponete questi tagliuoli uno sopra l'altro con simmetria su di un vassoio di rame o di porcellana che regga al fuoco, intramezzandoli con alcuni pezzetti di burro, e rosolateli alquanto nel forno da campagna per servirli caldi."
    },
    {
      "id": "379.0",
      "ricetta": 379,
      "titolo": "Fagiuolini e zucchine alla sautè",
      "capitolo": "Erbaggi e legumi",
      "posizione_chunk": 0,
      "score": 0.625,
      "testo": "Questi erbaggi così cucinati servono per lo più di contorno. ora la così detta cucina fine ha ridotto l'uso dei condimenti a una grande semplicità. Sarà più igienica, se vogliamo, e lo stomaco si sentirà più leggiero; ma il gusto ne scapita alquanto e viene a mancare quel certo stimolo che a molte persone è necessario per eccitare la digestione. Qui siamo in questo caso. Se trattasi di fagiuolini lessateli a metà, se di zucchini lasciateli crudi tagliati a spicchi o a tocchetti, metteteli a soffriggere nel burro quando questo, bollendo, avrà preso il color nocciuola. Per condimento mettete soltanto sale e pepe in poca quantità. Se dopo cotti in questa maniera vi aggiungerete un poco di sugo di carne oppure un poco della salsa di pomodoro N. 125 non sarete più nelle regole della cucina for…"
    },
    {
      "id": "619.1",
      "ricetta": 619,
      "titolo": "Cavallucci di Siena",
      "capitolo": "Pasticceria",
      "posizione_chunk": 1,
      "score": 0.624,
      "testo": "grammi 100. Arancio candito, grammi 50. Anaci, grammi 15. Spezie e cannella in polvere, grammi 5. Le noci tritatele alla grossezza della veccia all'incirca. L'arancio tagliatelo a dadettini. Lo zucchero mettetelo al fuoco con un terzo del suo peso di acqua e quando è ridotto a cottura di filo gettate in esso tutti gli ingredienti, mescolate e versate il composto caldo nella spianatoia sopra la farina per intriderla; ma per far questo vedrete che vi occorrerà dell'altra farina, la quale serve a ridurre la pasta consistente. Formate allora i cavallucci, dei quali, con questa dose, ne otterrete oltre a 40, e siccome, a motivo dello zucchero, questa pasta appiccica, spolverizzateli di farina alla superficie. Collocateli in una teglia e cuoceteli in bianco a moderato calore. State molto attent…"
    },
    {
      "id": "489.0",
      "ricetta": 489,
      "titolo": "Sparnocchie",
      "capitolo": "Piatti di pesce",
      "posizione_chunk": 0,
      "score": 0.623,
      "testo": "Le cicale mi rammentano le sparnocchie che, a prima vista, le rassomigliano; ma esaminato bene questo crostaceo ha la forma di un grosso gambero di mare del peso comunemente di 50 o 60 grammi. È di sapore più delicato dell'arigusta e, come questa, si usa mangiarlo lesso; ma perchè non perda sapore meglio è di arrostirlo in gratella, senza condimento alcuno, e dopo sgusciarlo e condirlo con olio, pepe, sale ed agro di limone. Le sparnocchie piccole si possono anche, come i gamberi, infarinare e friggerle così naturali, oppure nel modo indicato per le cicale."
    }
  ],
  "nota": "top_k ridotto da 50 a 10 (massimo consentito)"
}
(exit 0)
```

Log del server:

```
2026-11-18 09:55:29,014 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi top_k_max=10
2026-11-18 09:55:32,799 INFO rag.server_mcp ricerca esito=ok modalita=base query="gnocchi" top_k=50 filtro=- passaggi=10 ids=89.0,230.0,89.1,231.0,90.0,231.1,699.0,379.0,619.1,489.0 nota="top_k ridotto da 50 a 10 (massimo consentito)" ms=2333
```

## `rag.cliente_mcp "brodo" --filtro Dolciumi`

```
strumenti: search_documents
argomenti: {"query": "brodo", "filtro": "Dolciumi"}
esito: errore del tool
filtro "Dolciumi" non valido: deve essere il nome di un capitolo. Valori validi: Brodi, gelatina e sughi; Minestre in brodo; Minestre asciutte e di magro; Principii; Salse; Uova; Paste e pastelle; Ripieni; Fritti; Lesso; Tramessi; Umidi; Rifreddi; Erbaggi e legumi; Piatti di pesce; Arrosti; Pasticceria; Torte e dolci al cucchiaio; Siroppi; Conserve; Liquori; Gelati; Cose diverse
(exit 1)
```

Log del server:

```
2026-11-18 09:55:46,688 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi top_k_max=10
2026-11-18 09:55:48,134 INFO rag.server_mcp ricerca esito=errore:filtro_inesistente modalita=- query="brodo" top_k=5 filtro=Dolciumi passaggi=0 ids=- nota="" ms=0
```

## `rag.cliente_mcp "   "`

```
strumenti: search_documents
argomenti: {"query": " "}
esito: errore del tool
query è vuota: scrivi in `query` la domanda dell'utente.
(exit 1)
```

Log del server:

```
2026-11-18 09:55:59,740 INFO rag.server_mcp server di ricerca avviato (stdio) collezione=artusi top_k_max=10
2026-11-18 09:56:01,249 INFO rag.server_mcp ricerca esito=errore:query_vuota modalita=- query="" top_k=5 filtro=- passaggi=0 ids=- nota="" ms=0
```

