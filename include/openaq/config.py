"""Costanti di dominio e configurazione non segreta della pipeline OpenAQ Italia."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

OPENAQ_BASE_URL = "https://api.openaq.org/v3"
API_KEY_HEADER = "X-API-Key"

COUNTRY_ISO = "IT"

# Gli id parametro di OpenAQ v3. Verificato dal container su /v3/parameters/1.
PARAMETER_BY_ID: dict[int, str] = {1: "pm10", 2: "pm25"}

MEASUREMENT_TABLE = "measurement_hourly"
SENSOR_TABLE = "sensor"
STATE_TABLE = "ingestion_state"

BACKFILL_MONTHS_DEFAULT = 12

@dataclass(frozen=True) # frozen=True rende la dataclass immutabile dopo la creazione
class OpenAQCredentials:
    """Come raggiungere e autenticarsi su OpenAQ.

    Attributes:
        base_url: URL base dell'API, senza slash finale.
        api_key: Chiave da mettere nell'header `X-API-Key`.
    """

    base_url: str
    api_key: str

@dataclass(frozen=True)
class ClickHouseTarget:
    """Come raggiungere e autenticarsi su ClickHouse.

    Attributes:
        host: Hostname o IP del server ClickHouse.
        port: Porta TCP del server ClickHouse.
        username: Nome utente per l'autenticazione.
        password: Password per l'autenticazione.
    """

    host: str
    port: int
    username: str
    password: str


@dataclass(frozen=True)
class Settings:
    """Configurazione: cosa fare, non come autenticarsi.

    Le credenziali arrivano dalle Airflow Connection tramite `connections.py` e
    non passano da qui. È questa separazione che permette a questo modulo
    di girare senza contesto Airflow.

    Attributes:
        raw_database: Database ClickHouse del layer raw.
        analytics_database: Database ClickHouse dei modelli dbt.
        requests_per_minute: Tetto di richieste per singolo processo worker.
        page_size: Righe per pagina sugli endpoint di OpenAQ.
    """

    raw_database: str = "openaq_raw"
    analytics_database: str = "openaq_analytics"
    requests_per_minute: int = 25
    page_size: int = 1000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        """Costruisce le impostazioni a partire da un ambiente.

        Args:
            env: Mapping da cui leggere. Se `None`, usa `os.environ`. Poterlo
                passare è ciò che rende i test funzioni pure, senza toccare
                l'ambiente reale.

        Returns:
            Un'istanza con i valori letti, o i default dove la chiave manca.
        """
        env = os.environ if env is None else env

        return cls(
            raw_database=env.get("CLICKHOUSE_RAW_DATABASE", "openaq_raw"),
            analytics_database=env.get(
                "CLICKHOUSE_ANALYTICS_DATABASE", "openaq_analytics"
            ),
            requests_per_minute=int(env.get("OPENAQ_REQUESTS_PER_MINUTE", "25")),
            page_size=int(env.get("OPENAQ_PAGE_SIZE", "1000")),
        )