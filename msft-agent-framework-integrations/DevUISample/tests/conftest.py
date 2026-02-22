"""
conftest.py
===========
Shared pytest fixtures for the DevUI sample tests.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def mock_azure_env(monkeypatch: pytest.MonkeyPatch):
    """Patch environment so agent modules don't need real credentials in CI."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
