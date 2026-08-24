"""Client HTTP per OpenAQ v3: rate limiting, retry e paginazione.

RateLimiter — casi coperti dai test:
- chiamate sotto il limite: non dorme mai;
- finestra piena: dorme fino a quando la più vecchia ne esce;
- chiamata più vecchia della finestra: dimenticata, nessuna attesa;
- max_calls < 1: ValueError, non è una configurazione ma un errore.
"""

import time
from collections import deque
from typing import Callable


class RateLimiter:
    """Limitatore a finestra scorrevole.

    Tiene gli orari delle ultime `max_calls` chiamate. Quando la finestra è
    piena, dorme fino a quando la più vecchia ne esce. Orologio e sleep sono
    iniettabili per poter testare senza attese reali.

    Args:
        max_calls: Chiamate concesse nella finestra.
        period_seconds: Durata della finestra.
        clock: Funzione che restituisce secondi crescenti. `time.monotonic`
            e non `time.time` perché il secondo può saltare indietro.
        sleep: Funzione che attende N secondi.

    Raises:
        ValueError: Se `max_calls` è minore di 1.
    """

    def __init__(
        self,
        max_calls: int,
        period_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls deve essere almeno 1")

        self._max_calls = max_calls
        self._period = float(period_seconds)
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()

    def acquire(self) -> None:
        """Autorizza una richiesta, aspettando se la finestra è piena."""
        self._evict_expired()

        if len(self._calls) >= self._max_calls:
            wait = self._period - (self._clock() - self._calls[0])
            if wait > 0:
                self._sleep(wait)
            self._evict_expired()

        self._calls.append(self._clock())

    def _evict_expired(self) -> None:
        """Togli dall'elenco gli orari usciti dalla finestra."""
        cutoff = self._clock() - self._period
        while self._calls and self._calls[0] <= cutoff:
            self._calls.popleft()