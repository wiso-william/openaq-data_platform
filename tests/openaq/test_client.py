import pytest

from include.openaq.client import RateLimiter

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