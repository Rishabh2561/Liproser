import json

import httpx
from liproser.config import Settings
from liproser.providers import (
    _primary_draft_schema,
    _profile_schema,
    normalize_model,
    provider_failure_detail,
    provider_readiness,
)
from liproser.runtime_secrets import set_session_secret


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": json.dumps({"ok": True})}
                    ]
                }
            ],
            "usage": {"input_tokens": 4, "output_tokens": 4},
        }


class FakeClient:
    last_payload = None

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def post(self, _url, **kwargs):
        FakeClient.last_payload = kwargs["json"]
        return FakeResponse()


def test_openai_display_names_normalize_to_api_model_ids():
    assert normalize_model("openai", "Terra") == "gpt-5.6-terra"
    assert normalize_model("openai", "GPT-5.6 Luna") == "gpt-5.6-luna"
    assert normalize_model("openai", "GPT 5.6 Sol") == "gpt-5.6-sol"


def test_generation_schemas_keep_profile_and_primary_draft_contracts_distinct():
    assert "suggestions" in _profile_schema()["properties"]
    assert set(_primary_draft_schema()["required"]) == {"hook", "body", "cta", "claims"}


def test_provider_failures_are_actionable_without_exposing_response_bodies():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    network = httpx.ConnectError("socket detail", request=request)
    assert "internet, proxy, or firewall" in provider_failure_detail("openai", network)

    unauthorized = httpx.HTTPStatusError(
        "sensitive response detail",
        request=request,
        response=httpx.Response(401, request=request),
    )
    detail = provider_failure_detail("openai", unauthorized)
    assert detail == "OpenAI rejected the API key. Check the key and try again."
    assert "sensitive" not in detail


def test_openai_probe_uses_session_key_structured_output_and_no_storage(monkeypatch):
    monkeypatch.setattr("liproser.providers.httpx.Client", FakeClient)
    set_session_secret("openai", "synthetic-provider-value-for-tests")
    settings = Settings(_env_file=None, openai_api_key="")
    ready, detail = provider_readiness(settings, "openai", "Terra")
    assert ready is True
    assert "gpt-5.6-terra" in detail
    assert FakeClient.last_payload["model"] == "gpt-5.6-terra"
    assert FakeClient.last_payload["store"] is False
    assert FakeClient.last_payload["text"]["format"]["type"] == "json_schema"
