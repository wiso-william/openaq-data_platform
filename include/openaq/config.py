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