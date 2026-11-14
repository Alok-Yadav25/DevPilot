"""Redact fully formatted output, including exception tracebacks and HTTP logs."""

import logging
from collections.abc import Iterable

from app.security import Redactor


class RedactingFormatter(logging.Formatter):
    def __init__(self, redact: Redactor, original: logging.Formatter | None = None) -> None:
        super().__init__()
        self.redact = redact
        self.original = original or logging.Formatter("%(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        # Format first: args, exception chains, and custom formatter fields must
        # all pass through the same boundary before anything reaches the stream.
        return self.redact(self.original.format(record))


def configure_redacted_logging(secrets: Iterable[str]) -> None:
    redact = Redactor(secrets)
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    loggers = [
        root,
        *(
            logging.getLogger(name)
            for name in (
                "app",
                "uvicorn",
                "uvicorn.error",
                "uvicorn.access",
                "httpx",
                "httpcore",
            )
        ),
    ]
    seen: set[int] = set()
    for logger in loggers:
        for handler in logger.handlers:
            if id(handler) in seen:
                continue
            seen.add(id(handler))
            original = handler.formatter
            if isinstance(original, RedactingFormatter):
                original = original.original
            handler.setFormatter(RedactingFormatter(redact, original))
