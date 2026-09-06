import json

from liproser.config import Settings
from liproser.providers import normalize_model, provider_readiness
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


def test_terra_display_name_normalizes_to_api_model_id():
    assert normalize_model("openai", "Terra") == "gpt-5.6-terra"


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
