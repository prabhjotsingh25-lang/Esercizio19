"""Collegamento al modello servito da LM Studio (API compatibile con OpenAI)."""
from langchain_openai import ChatOpenAI

from assistente.config import Configurazione


def crea_modello(config: Configurazione) -> ChatOpenAI:
    """Crea il client verso LM Studio; la chiave è un segnaposto, il server non la controlla."""
    return ChatOpenAI(
        base_url=config.base_url,
        model=config.modello,
        api_key="lm-studio",
        timeout=120,
    )
