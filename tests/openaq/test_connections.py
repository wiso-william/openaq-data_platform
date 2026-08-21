from types import SimpleNamespace

import pytest

from include.openaq import connections


def _fake_conn(**overrides):
    """Imita una Connection di Airflow: gli attributi non impostati sono None."""
    fields = {"host": None, "port": None, "login": None, "password": None}
    fields.update(overrides)
    # SimpleNamespace è un oggetto che accetta qualsiasi attributo, utile per testare senza dipendere da Airflow
    return SimpleNamespace(**fields) # SimpleNamespace.host = None


def _patch(monkeypatch, conn):
    """Sostituisce l'unico punto che tocca Airflow."""
    # Monkeypatch è un fixture di pytest che permette di sostituire funzioni o attributi durante il test
    monkeypatch.setattr(connections, "_get_connection", lambda conn_id: conn)


def test_openaq_credentials_reads_host_and_key(monkeypatch):
    """Verifica che `openaq_credentials` legga host e password dalla Connection."""
    _patch(monkeypatch, _fake_conn(host="https://api.openaq.org/v3", password="abc123"))

    creds = connections.openaq_credentials()

    assert creds.base_url == "https://api.openaq.org/v3"
    assert creds.api_key == "abc123"


def test_openaq_credentials_strips_a_trailing_slash(monkeypatch):
    """Verifica che `openaq_credentials` rimuova lo slash finale dall'host."""
    _patch(monkeypatch, _fake_conn(host="https://api.openaq.org/v3/", password="abc123"))

    assert connections.openaq_credentials().base_url == "https://api.openaq.org/v3"


def test_openaq_credentials_falls_back_to_the_default_base_url(monkeypatch):
    """Verifica che `openaq_credentials` usi l'host di default se la Connection non lo dichiara."""
    _patch(monkeypatch, _fake_conn(password="abc123"))

    assert connections.openaq_credentials().base_url == connections.OPENAQ_BASE_URL


def test_openaq_credentials_requires_a_password(monkeypatch):
    """Una Connection senza chiave API è un errore di configurazione, non un default."""
    _patch(monkeypatch, _fake_conn(host="https://api.openaq.org/v3", password=""))

    with pytest.raises(ValueError, match="openaq_default"):
        connections.openaq_credentials()


def test_clickhouse_target_maps_connection_fields(monkeypatch):
    """I quattro campi della Connection finiscono nei quattro campi del target."""
    _patch(
        monkeypatch,
        _fake_conn(host="db_clickhouse", port=8123, login="openaq", password="segreto"),
    )

    target = connections.clickhouse_target()

    assert target.host == "db_clickhouse"
    assert target.port == 8123
    assert target.username == "openaq"
    assert target.password == "segreto"


def test_clickhouse_target_applies_defaults(monkeypatch):
    """Con una Connection vuota si ottiene il ClickHouse locale del compose."""
    _patch(monkeypatch, _fake_conn())

    target = connections.clickhouse_target()

    assert target.host == "db_clickhouse"
    assert target.port == 8123
    assert target.username == "default"


def test_clickhouse_target_accepts_an_empty_password(monkeypatch):
    """Un ClickHouse locale senza password è una configurazione valida."""
    _patch(monkeypatch, _fake_conn(host="db_clickhouse", port=8123, login="openaq"))

    assert connections.clickhouse_target().password == ""