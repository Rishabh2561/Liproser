from __future__ import annotations

import httpx

from .config import Settings


def provider_readiness(settings: Settings, provider: str, model: str) -> tuple[bool, str]:
    if provider == "fake":
        return True, "Fake provider satisfies the structured-output contract"
    if provider == "openai":
        if not settings.openai_api_key:
            return False, "OPENAI_API_KEY is not configured"
        payload = {
            "model": model,
            "input": "Return a JSON object with ok set to true.",
            "store": False,
            "max_output_tokens": 30,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "provider_check",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                }
            },
        }
        with httpx.Client(timeout=20) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json=payload,
            )
            response.raise_for_status()
        return True, "OpenAI Responses structured-output check passed with store=false"
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return False, "ANTHROPIC_API_KEY is not configured"
        payload = {
            "model": model,
            "max_tokens": 30,
            "messages": [{"role": "user", "content": 'Reply with exactly {"ok":true}.'}],
        }
        with httpx.Client(timeout=20) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
            )
            response.raise_for_status()
        return True, "Claude Messages provider check passed"
    if provider == "ollama":
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Return JSON with ok true"}],
            "stream": False,
            "format": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
        }
        with httpx.Client(timeout=20) as client:
            response = client.post(f"{settings.ollama_base_url.rstrip('/')}/api/chat", json=payload)
            response.raise_for_status()
        return True, "Ollama structured-output check passed"
    return False, "Unsupported provider"
