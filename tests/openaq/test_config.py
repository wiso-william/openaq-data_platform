"""Test della configurazione non segreta della pipeline OpenAQ.

Questi test non toccano nulla di esterno. 
È la conseguenza voluta del confine fra `config.py` e `connections.py`.
"""

from include.openaq.config import PARAMETER_BY_ID, Settings


def test_parameter_ids_cover_pm10_and_pm25():
    """Verifica la mappa fra id parametro OpenAQ e nomi di dominio.

    Su questa mappa si basa il filtro che scarta i sensori non PM(62% da /v3/locations).
    Se si aggiungesse una voce qui — per esempio `pm1`,  cambierebbe senza avviso il contenuto del dataset. 
    Con questo test si può notare subito e decidere se accettare o meno la modifica.
    """
    assert PARAMETER_BY_ID == {1: "pm10", 2: "pm25"}


def test_settings_from_env_reads_every_field():
    """Verifica che `from_env` legga l'ambiente e converta i tipi.

    I valori sono volutamente diversi dai default altrimenti il test
    passerebbe sempre e sarebbe inutile

    Note:
        Nel dizionario i numeri sono stringhe, negli assert sono interi: le
        variabili d'ambiente sono sempre stringhe, quindi questo verifica anche
        la conversione.
    """
    env = {
        "CLICKHOUSE_RAW_DATABASE": "raw_<-^-^->",
        "CLICKHOUSE_ANALYTICS_DATABASE": "analytics_<-^-^->",
        "OPENAQ_REQUESTS_PER_MINUTE": "47",
        "OPENAQ_PAGE_SIZE": "254",
    }

    settings = Settings.from_env(env)

    assert settings.raw_database == "raw_<-^-^->"
    assert settings.analytics_database == "analytics_<-^-^->"
    assert settings.requests_per_minute == 47
    assert settings.page_size == 254


def test_settings_from_env_applies_defaults():
    """Verifica i default quando l'ambiente non dichiara nulla.

    Il limite massimo di richieste per minuto di OpenAQ è 60. `requests_per_minute` vale 25 e
    non 60 perché il limitatore vive nel processo del worker e il DAG esegue
    fino a 2 task di ingestion in parallelo: 25 * 2 = 50 richieste al minuto,
    Cambiando questi parametri il parallelismo andrebbe ricalcolato, ed è la ragione per
    cui è configurabile e non costante.
    """
    settings = Settings.from_env({})

    assert settings.raw_database == "openaq_raw"
    assert settings.analytics_database == "openaq_analytics"
    assert settings.requests_per_minute == 25
    assert settings.page_size == 1000


def test_settings_carry_no_credentials():
    """Verifica che `Settings` non abbia campi per le credenziali.

    Test di un'assenza, non voglio che il codice applicativo legga i segreti dell' ambiente. 
    Airflow fa già un buon lavoro nel nascondere i segreti
    ma voglio essere più sicuro che questo non avvenga in nessun caso.

    Note:
        `__dataclass_fields__` è generato da Python su ogni dataclass e contiene
        i nomi dei campi.
    """
    fields = set(Settings.__dataclass_fields__)

    assert not fields & {"api_key", "clickhouse_password", "password"}