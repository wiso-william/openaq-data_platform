from types import SimpleNamespace

import pytest

from include.openaq import connections


def _fake_conn(**overrides):
    """Imita una Connection di Airflow: gli attributi non impostati sono None."""
    fields = {"host": None, "port": None, "login": None, "password": None}
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _patch(monkeypatch, conn):
    """Sostituisce l'unico punto che tocca Airflow."""
    monkeypatch.setattr(connections, "_get_connection", lambda conn_id: conn)