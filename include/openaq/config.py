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

# Creo le dataclass
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