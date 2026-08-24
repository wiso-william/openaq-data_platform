"""Client HTTP per OpenAQ v3: rate limiting, retry e paginazione.

RateLimiter — casi coperti dai test:
- chiamate sotto il limite: non dorme mai;
- finestra piena: dorme fino a quando la più vecchia ne esce;
- chiamata più vecchia della finestra: dimenticata, nessuna attesa;
- max_calls < 1: ValueError, non è una configurazione ma un errore.

OpenAQClient.get — casi coperti dai test:
- richiesta normale: manda la chiave nell'header X-API-Key;
- 429 con `retry-after`: aspetta i secondi indicati e riprova;
- 429 con solo `x-ratelimit-reset`: usa quello, perché OpenAQ non manda
  `retry-after` (verificato dal container);
- 500 poi 502 poi 200: backoff esponenziale, 2s e poi 4s;
- tentativi esauriti: OpenAQError con lo stato dentro il messaggio;
- 422: nessun retry e una sola chiamata, la richiesta è malformata.
"""

import logging
import time
from collections import deque
from typing import Any, Callable

import requests

from include.openaq.config import API_KEY_HEADER, OPENAQ_BASE_URL

logger = logging.getLogger(__name__)


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

# Server error or requested new data too quickly
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class OpenAQError(RuntimeError):
    """Errore non recuperabile parlando con l'API OpenAQ."""


class OpenAQClient:
    """Wrapper minimale su OpenAQ v3.

    Mette la chiave nell'header, rispetta il rate
    limit, e riprova quando l'errore è transitorio.

    Args:
        api_key: Chiave da mettere nell'header `X-API-Key`.
        base_url: URL base dell'API. Lo slash finale viene rimosso, perché i
            path vengono concatenati e iniziano già con `/`.
        session: Oggetto con un metodo `get(url, params, headers, timeout)`. Se
            `None`, una `requests.Session()`. Iniettabile per i test.
        rate_limiter: Freno interrogato prima di ogni richiesta, ritentativi
            compresi. Se `None`, un `RateLimiter(25)`.
        max_retries: Tentativi **totali**, non aggiuntivi: con 3 la richiesta
            viene inviata al massimo tre volte.
        backoff_base_seconds: Base del backoff esponenziale, usata solo quando
            il server non dice quanto aspettare.
        timeout_seconds: Secondi oltre i quali la singola richiesta viene
            abbandonata.
        sleep: Funzione di attesa, iniettabile per i test.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = OPENAQ_BASE_URL,
        session: Any | None = None,
        rate_limiter: RateLimiter | None = None,
        max_retries: int = 5,
        backoff_base_seconds: float = 2.0,
        timeout_seconds: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {API_KEY_HEADER: api_key, "Accept": "application/json"}
        self._session = session if session is not None else requests.Session()
        self._limiter = rate_limiter if rate_limiter is not None else RateLimiter(25)
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds
        self._timeout = timeout_seconds
        self._sleep = sleep

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Esegue una GET, riprovando sugli errori transitori.

        Args:
            path: Percorso a partire dalla base, per esempio `/parameters/1`.
            params: Parametri di query.

        Returns:
            dict:Il corpo della risposta già decodificato da JSON.

        Raises:
            OpenAQError: Se lo stato non è ritentabile (per esempio 422, che
                significa richiesta malformata: ripeterla identica fallirebbe
                di nuovo) oppure se i tentativi si esauriscono.
        """
        url = f"{self._base_url}{path}"

        for attempt in range(1, self._max_retries + 1):
            # Il freno va interrogato a ogni tentativo, non solo al primo:
            # altrimenti una raffica di retry sfonderebbe il limite proprio
            # mentre il server ci sta dicendo che stiamo esagerando.
            self._limiter.acquire()
            response = self._session.get(
                url, params=params, headers=self._headers, timeout=self._timeout
            )

            if response.status_code == 200:
                return response.json()

            if (
                response.status_code not in RETRYABLE_STATUS
                or attempt == self._max_retries
            ):
                raise OpenAQError(
                    f"GET {path} ha risposto {response.status_code} "
                    f"(tentativo {attempt}/{self._max_retries}): {response.text[:200]}"
                )

            wait = self._retry_delay(response, attempt)
            logger.warning(
                "GET %s ha risposto %s, riprovo tra %.1fs (tentativo %s/%s)",
                path,
                response.status_code,
                wait,
                attempt,
                self._max_retries,
            )
            self._sleep(wait)

        # Irraggiungibile: l'ultimo tentativo esce dal ramo sopra. Sta qui perché
        # un `for` senza `return` finale è una firma che mente.
        raise OpenAQError(f"GET {path}: tentativi esauriti")

    def _retry_delay(self, response: Any, attempt: int) -> float:
        """Quanto aspettare prima del prossimo tentativo.

        Preferisce quello che dice il server, in ordine di precisione. OpenAQ
        **non manda `retry-after`**: manda `x-ratelimit-reset` con i secondi che
        restano alla finestra corrente. Un client che cerca solo `retry-after` e
        ripiega sull'esponenziale butta l'informazione migliore che ha, e su un
        429 finisce per aspettare troppo o troppo poco.

        Args:
            response: La risposta da cui leggere gli header.
            attempt: Numero del tentativo appena fallito, da 1.

        Returns:
            float:I secondi di attesa.
        """
        for header in ("retry-after", "x-ratelimit-reset"):
            raw = response.headers.get(header)
            if not raw:
                continue
            try:
                # max(..., 0) perché un header con un valore negativo o un
                # orologio sfasato non deve produrre un'attesa negativa.
                return max(float(raw), 0.0)
            except (TypeError, ValueError):
                continue

        return self._backoff_base * (2 ** (attempt - 1))