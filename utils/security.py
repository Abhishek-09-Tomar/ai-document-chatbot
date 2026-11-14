"""Small, server-side budgets and safe diagnostics. Never log user content or keys."""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import logging
import threading
import time

MAX_QUERY_CHARS = 2000
MAX_SOURCES = 4
MAX_QUERIES = 20
COOLDOWN_SECONDS = 2.0
MAX_PROCESSING_REQUESTS = 10
LOGGER = logging.getLogger('document_chat.security')
_PROCESS_SLOTS = threading.BoundedSemaphore(2)


class BudgetError(ValueError):
    """An intentionally safe, user-facing resource-limit message."""


def log_failure(event, error):
    response = getattr(error, 'response', None)
    LOGGER.warning('%s error_type=%s http_status=%s',
                   event, type(error).__name__, getattr(response, 'status_code', None))


@dataclass
class SessionBudget:
    queries: int = 0
    processing: int = 0
    last_query: float = float('-inf')
    last_processing: float = float('-inf')

    def consume(self, action, now=None):
        now = time.monotonic() if now is None else now
        if action == 'query':
            count, previous, maximum = self.queries, self.last_query, MAX_QUERIES
        elif action == 'processing':
            count, previous, maximum = self.processing, self.last_processing, MAX_PROCESSING_REQUESTS
        else:
            raise ValueError('Unknown action.')
        if count >= maximum:
            raise BudgetError('The session limit has been reached. Please come back later.')
        if now - previous < COOLDOWN_SECONDS:
            raise BudgetError('Please wait at least 2 seconds before trying again.')
        if action == 'query':
            self.queries += 1
            self.last_query = now
        else:
            self.processing += 1
            self.last_processing = now


@contextmanager
def processing_slot():
    if not _PROCESS_SLOTS.acquire(blocking=False):
        raise BudgetError('The server is busy processing documents. Please try again shortly.')
    try:
        yield
    finally:
        _PROCESS_SLOTS.release()


def select_inference_credential(personal, server, authenticated):
    """Public visitors cannot spend the operator's credential."""
    if personal:
        return personal, False
    return (server, True) if authenticated and server else (None, False)


class HostedBudget:
    """Bound per-key calls, total shared spending and concurrent hosted requests."""
    def __init__(self):
        self.lock = threading.Lock()
        self.records = {}
        self.shared_calls = 0
        self.inflight = threading.BoundedSemaphore(2)

    @contextmanager
    def reserve(self, credential, shared=False, now=None):
        now = time.monotonic() if now is None else now
        digest = sha256(credential.encode()).hexdigest()
        if not self.inflight.acquire(blocking=False):
            raise BudgetError('Hosted AI is busy. Showing source excerpts instead.')
        try:
            with self.lock:
                self.records = {k: v for k, v in self.records.items() if now - v[0] < 3600}
                if digest not in self.records and len(self.records) >= 256:
                    raise BudgetError('Hosted AI has reached its server limit.')
                start, count, last = self.records.get(digest, (now, 0, float('-inf')))
                if count >= 20 or now - last < COOLDOWN_SECONDS or (shared and self.shared_calls >= 40):
                    raise BudgetError('Hosted AI has reached its request limit. Showing source excerpts instead.')
                self.records[digest] = (start, count + 1, now)
                if shared:
                    self.shared_calls += 1
            yield
        finally:
            self.inflight.release()


HOSTED_BUDGET = HostedBudget()
