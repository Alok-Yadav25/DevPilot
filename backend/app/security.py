import re
from collections.abc import Iterable
from pathlib import PurePosixPath

_SECRET = re.compile(
    r"(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]{10,}|gsk_[A-Za-z0-9]{10,})"
)
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class Redactor:
    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self.secrets = sorted((s for s in secrets if s), key=len, reverse=True)

    def contains_secret(self, value: str) -> bool:
        return bool(_SECRET.search(value)) or any(secret in value for secret in self.secrets)

    def __call__(self, value: str) -> str:
        value = _ANSI.sub("", value)
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        value = _SECRET.sub("[REDACTED]", value)
        value = re.sub(
            r"((?:https?|postgres(?:ql)?(?:\+\w+)?)://)[^\s/@]+(?::[^\s/@]*)?@",
            r"\1[REDACTED]@",
            value,
        )
        value = re.sub(
            r"""(?i)(authorization["']?\s*[:=]\s*["']?(?:bearer|basic)\s+)[^\s"',}]+""",
            r"\1[REDACTED]",
            value,
        )
        return _CONTROL.sub("", value.replace("\r", ""))


def sensitive_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(
        p.startswith(".")
        or p.lower() in {"credentials", "secrets", "id_rsa", "id_ed25519"}
        or p.lower().endswith((".pem", ".key", ".p12"))
        for p in parts
    )
