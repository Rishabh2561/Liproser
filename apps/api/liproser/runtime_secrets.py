from __future__ import annotations

from threading import RLock

_lock = RLock()
_session_secrets: dict[str, str] = {}


def set_session_secret(provider: str, value: str) -> None:
    with _lock:
        _session_secrets[provider] = value


def get_session_secret(provider: str) -> str:
    with _lock:
        return _session_secrets.get(provider, "")


def clear_session_secret(provider: str) -> bool:
    with _lock:
        return _session_secrets.pop(provider, None) is not None


def clear_all_session_secrets() -> None:
    with _lock:
        _session_secrets.clear()
