"""Match candidate capture's Git configuration policy during fixture setup."""

import pytest


@pytest.fixture(autouse=True)
def isolated_git_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
