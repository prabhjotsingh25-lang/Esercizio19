"""Riassunto: quando la cronologia è lunga, i messaggi vecchi diventano un riassunto."""
from collections.abc import Callable, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from assistente.contesto import e_domanda, e_indicazione, riga_di_testo

ISTRUZIONI_RIASSUNTO = (
    "Aggiorni il riassunto di una conversazione fra un utente e un assistente di laboratorio. "
    "Non rispondere all'utente: scrivi soltanto il riassunto.\n"
    "La prima riga inizia con «Utente:» e riporta i fatti che l'utente ha detto di sé, per "
    "esempio «Utente: si chiama Anna, lavora nel laboratorio di chimica.»; se non ne ha detti, "
    "scrivi «Utente: nessuna informazione.». Poi, in al massimo dieci frasi e nella lingua "
    "della conversazione, riassumi il resto: dati e risultati, richieste ancora in sospeso.\n"
    "Unisci il riassunto precedente e i nuovi messaggi: non perdere i fatti del riassunto "
    "precedente."
)

# (riassunto precedente, messaggi da togliere) -> nuovo riassunto
Riassuntore = Callable[[str, Sequence[BaseMessage]], str]


def punto_di_taglio(messaggi: Sequence[BaseMessage], recenti: int) -> int:
    """Indice del primo messaggio da tenere; 0 se non c'è niente da riassumere.

    Si parte da «ultimi `recenti`» e si torna indietro fino alla domanda dell'utente più
    vicina: il taglio cade solo fra un turno e l'altro, quindi una chiamata a uno strumento
    non resta mai separata dal suo ToolMessage né un'indicazione dalla sua bozza.
    """
    for i in range(max(len(messaggi) - recenti, 0), -1, -1):
        if e_domanda(messaggi[i]):
            return i
    return 0


def dialogo_da_riassumere(messaggi: Sequence[BaseMessage]) -> str:
    """Domande e risposte accettate; senza strumenti, indicazioni e bozze scartate."""
    righe = []
    for i, m in enumerate(messaggi):
        successivo = messaggi[i + 1] if i + 1 < len(messaggi) else None
        if isinstance(m, AIMessage) and successivo is not None and e_indicazione(successivo):
            continue  # bozza rifiutata dal revisore
        riga = riga_di_testo(m)
        if riga is not None:
            righe.append(riga)
    return "\n".join(righe)


def crea_riassuntore(modello: BaseChatModel) -> Riassuntore:
    """Riassuntore basato sul modello; gli errori di connessione passano al chiamante."""
    def riassumi(precedente: str, messaggi: Sequence[BaseMessage]) -> str:
        risposta = modello.invoke([
            SystemMessage(ISTRUZIONI_RIASSUNTO),
            HumanMessage(f"Riassunto precedente:\n{precedente.strip() or '(nessuno)'}\n\n"
                         f"Nuovi messaggi:\n{dialogo_da_riassumere(messaggi)}")])
        return risposta.content.strip() if isinstance(risposta.content, str) else ""

    return riassumi
