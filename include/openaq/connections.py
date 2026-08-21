"""Adattatore fra le Airflow Connection e i tipi del dominio.

È l'unico modulo di `include/openaq/` che conosce Airflow, e l'import è locale
alla funzione: importare questo file non importa Airflow, quindi i test girano
senza contesto e rapidamente.

I value object stanno in `config.py` e non qui.

I seguenti casi di test sono previsti e coperti:
- La Connection non ha host: si usa il default.
- La Connection ha uno slash finale nell'host: lo si rimuove.
- La Connection non ha baseurl: si usa il default.
- La Connection non ha password: si alza un'eccezione, perché senza chiave API
  la pipeline non funziona in nessuno scenario.
- La Connection non ha port, login o password: si usano i default per il
    ClickHouse locale del `docker-compose.override.yml`.
- La Connection ha una password vuota: si usa la password vuota per il
    ClickHouse locale del `docker-compose.override.yml`.
"""



from include.openaq.config import (
    OPENAQ_BASE_URL,
    ClickHouseTarget,
    OpenAQCredentials,
)

OPENAQ_CONN_ID = "openaq_default"
CLICKHOUSE_CONN_ID = "clickhouse_default"


def _get_connection(conn_id: str):
    """Unico punto di contatto con Airflow, e unico punto da sostituire nei test.

    Args:
        conn_id: Identificatore della Connection, per esempio `openaq_default`.

    Returns:
        L'oggetto Connection di Airflow.
    """
    from airflow.sdk import BaseHook

    return BaseHook.get_connection(conn_id)


def openaq_credentials(conn_id: str = OPENAQ_CONN_ID) -> OpenAQCredentials:
    """Traduce una Connection nelle credenziali OpenAQ.

    La chiave API sta nel campo `password` e non negli extra: `password` è
    mascherato per costruzione dalla UI e dai log di Airflow.

    Args:
        conn_id: Connection da leggere.

    Returns:
        Le credenziali, con `base_url` privo di slash finale.

    Raises:
        ValueError: Se la Connection non ha una password. Una pipeline senza
            chiave API non funziona in nessuno scenario: meglio fallire qui,
            nominando la Connection, che ricevere un 401 dentro un task.
    """
    conn = _get_connection(conn_id)

    if not conn.password:
        raise ValueError(f"La Connection {conn_id!r} non ha una chiave API")

    base_url = conn.host or OPENAQ_BASE_URL
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    return OpenAQCredentials(base_url=base_url, api_key=conn.password)


def clickhouse_target(conn_id: str = CLICKHOUSE_CONN_ID) -> ClickHouseTarget:
    """Traduce una Connection nel target ClickHouse.

    Nessun campo è obbligatorio: i default puntano al ClickHouse locale del
    `docker-compose.override.yml`. Una password vuota è una configurazione
    valida per un servizio locale, non un errore — al contrario della chiave
    OpenAQ.

    Args:
        conn_id: Connection da leggere.

    Returns:
        Il target, con i default applicati ai campi non dichiarati.
    """

    conn = _get_connection(conn_id)

    host = conn.host or "localhost"
    port = conn.port or 8123
    username = conn.login or "default"
    password = conn.password or ""

    return ClickHouseTarget(host=host, port=port, username=username, password=password)