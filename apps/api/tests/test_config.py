import pytest
from liproser.config import Settings
from pydantic import ValidationError


def test_personal_mode_accepts_loopback():
    settings = Settings(
        _env_file=None, app_env="personal", personal_mode=True, app_bind_host="127.0.0.1"
    )
    assert settings.personal_mode is True


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.4", "example.com"])
def test_personal_mode_rejects_public_binding(host):
    with pytest.raises(ValidationError, match="loopback"):
        Settings(_env_file=None, app_env="personal", personal_mode=True, app_bind_host=host)


def test_personal_mode_rejects_production():
    with pytest.raises(ValidationError, match="production"):
        Settings(
            _env_file=None, app_env="production", personal_mode=True, app_bind_host="127.0.0.1"
        )
