import time
from collections import defaultdict

from app.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Simple token bucket rate limiter per endpoint."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str = "default") -> bool:
        now = time.time()
        cutoff = now - self.window
        self.requests[key] = [t for t in self.requests[key] if t > cutoff]

        if len(self.requests[key]) >= self.max_requests:
            logger.warning(f"Rate limit hit for {key}")
            return False

        self.requests[key].append(now)
        return True

    def remaining(self, key: str = "default") -> int:
        now = time.time()
        cutoff = now - self.window
        self.requests[key] = [t for t in self.requests[key] if t > cutoff]
        return max(0, self.max_requests - len(self.requests[key]))
