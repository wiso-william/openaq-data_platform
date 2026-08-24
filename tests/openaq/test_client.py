import pytest

from include.openaq.client import OpenAQClient, OpenAQError, RateLimiter

class FakeClock:
    """Orologio e sleep finti, così i test sono istantanei e deterministici."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_rate_limiter_sleeps_until_the_oldest_call_leaves_the_window():
    """Con la finestra piena, l'attesa è esattamente il tempo che manca."""
    clock = FakeClock()
    limiter = RateLimiter(
        max_calls=2, period_seconds=60, clock=clock.monotonic, sleep=clock.sleep
    )

    limiter.acquire()          # t=1000
    clock.now += 10            # avanzo l'orologio a mano: t=1010
    limiter.acquire()          # t=1010
    limiter.acquire()          # finestra piena: deve aspettare

    assert clock.slept == [50.0]

def test_rate_limiter_allows_calls_up_to_the_limit_without_sleeping():
    """Sotto il limite non c'è nessuna attesa."""
    clock = FakeClock()
    limiter = RateLimiter(
        max_calls=3, period_seconds=60, clock=clock.monotonic, sleep=clock.sleep
    )

    for _ in range(3):
        limiter.acquire()

    assert clock.slept == []


def test_rate_limiter_forgets_calls_older_than_the_window():
    """Una chiamata uscita dalla finestra non occupa più il budget."""
    clock = FakeClock()
    limiter = RateLimiter(
        max_calls=1, period_seconds=60, clock=clock.monotonic, sleep=clock.sleep
    )

    limiter.acquire()      # t=1000
    clock.now += 61        # t=1061: la chiamata di 1000 è fuori finestra
    limiter.acquire()

    assert clock.slept == []


def test_rate_limiter_rejects_a_max_calls_below_one():
    """Un limitatore che concede zero chiamate è un errore di configurazione."""
    with pytest.raises(ValueError, match="max_calls"):
        RateLimiter(max_calls=0)


class FakeResponse:
    """Imita una risposta di `requests`: la superficie che il client usa."""

    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"meta": {}, "results": []}
        self.headers = headers or {}
        self.text = "fake response body"

    def json(self):
        return self._payload


class FakeSession:
    """Restituisce risposte da una coda e registra le chiamate ricevute."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if not self._responses:
            # Un finto generoso nasconde i bug: se il client chiama piu' volte
            # di quanto il test prevede, il test deve dirlo.
            raise AssertionError("chiamata HTTP inattesa: coda risposte esaurita")
        return self._responses.pop(0)


def _client_and_clock(session, **kwargs):
    """Costruisce un client con orologio finto e freno praticamente disattivato.

    `max_calls=1000` serve a non far entrare le attese del rate limiter in
    `clock.slept`: qui stiamo esaminando i retry, non il freno.
    """
    clock = FakeClock()
    client = OpenAQClient(
        api_key="abc123",
        session=session,
        rate_limiter=RateLimiter(
            max_calls=1000, clock=clock.monotonic, sleep=clock.sleep
        ),
        sleep=clock.sleep,
        **kwargs,
    )
    return client, clock


def test_get_sends_the_api_key_header():
    """La chiave viaggia nell'header `X-API-Key`, su ogni richiesta."""
    captured = {}

    class HeaderSpySession(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None):
            captured.update(headers or {})
            return super().get(url, params=params, headers=headers, timeout=timeout)

    session = HeaderSpySession(
        [FakeResponse(payload={"meta": {}, "results": [{"id": 1}]})]
    )
    client, _ = _client_and_clock(session)

    client.get("/parameters/1")

    assert captured["X-API-Key"] == "abc123"


def test_get_retries_on_429_and_honours_retry_after():
    """Con `retry-after` il client aspetta esattamente i secondi indicati."""
    session = FakeSession(
        [
            FakeResponse(status_code=429, headers={"retry-after": "7"}),
            FakeResponse(payload={"meta": {}, "results": [{"id": 1}]}),
        ]
    )
    client, clock = _client_and_clock(session)

    payload = client.get("/parameters/1")

    assert payload["results"] == [{"id": 1}]
    assert clock.slept == [7.0]


def test_get_uses_the_rate_limit_reset_when_retry_after_is_absent():
    """OpenAQ non manda `retry-after`: manda `x-ratelimit-reset`.

    Verificato dal container: gli header sono `X-Ratelimit-Limit`,
    `-Remaining`, `-Used`, `-Reset`. Nessun `retry-after`.
    """
    session = FakeSession(
        [
            FakeResponse(status_code=429, headers={"x-ratelimit-reset": "37"}),
            FakeResponse(payload={"meta": {}, "results": [{"id": 1}]}),
        ]
    )
    client, clock = _client_and_clock(session)

    client.get("/parameters/1")

    assert clock.slept == [37.0]


def test_get_retries_on_500_with_exponential_backoff():
    """Senza indicazioni dal server, l'attesa raddoppia a ogni tentativo."""
    session = FakeSession(
        [
            FakeResponse(status_code=500),
            FakeResponse(status_code=502),
            FakeResponse(payload={"meta": {}, "results": []}),
        ]
    )
    client, clock = _client_and_clock(session, backoff_base_seconds=2.0)

    client.get("/parameters/1")

    assert clock.slept == [2.0, 4.0]


def test_get_raises_after_exhausting_retries():
    """`max_retries` sono tentativi totali: con 3 si chiama tre volte, poi si alza."""
    session = FakeSession([FakeResponse(status_code=500) for _ in range(3)])
    client, _ = _client_and_clock(session, max_retries=3)

    with pytest.raises(OpenAQError, match="500"):
        client.get("/parameters/1")

    assert len(session.calls) == 3


def test_get_does_not_retry_on_422():
    """Un 422 dice che la richiesta e' malformata: ripeterla e' garantito fallire."""
    session = FakeSession([FakeResponse(status_code=422)])
    client, _ = _client_and_clock(session)

    with pytest.raises(OpenAQError, match="422"):
        client.get("/sensors/1/hours")

    # L'assert che conta: senza questo, il test passerebbe anche se il client
    # avesse riprovato cinque volte prima di arrendersi.
    assert len(session.calls) == 1
