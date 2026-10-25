"""Sandbox lifecycle: one sandbox per agent run, deleted when the run ends."""

from __future__ import annotations

import logging
import os
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Protocol

from dotenv import load_dotenv

from sandbox_agent.config import ConfigError

log = logging.getLogger(__name__)

LABEL_APP = "sandbox-agent"


@dataclass(frozen=True)
class SandboxSpec:
    """Resource shape for one sandbox. Defaults match the service's M tier."""

    disk: str = "ubuntu"
    cpu: str = "1000m"
    memory: str = "2048Mi"
    auto_suspend_seconds: int = 300


@dataclass(frozen=True)
class SandboxSettings:
    subscription_id: str
    resource_group: str
    sandbox_group: str
    region: str

    @classmethod
    def from_env(cls) -> "SandboxSettings":
        load_dotenv()
        return cls(
            subscription_id=_required("AZURE_SUBSCRIPTION_ID"),
            resource_group=_required("AZURE_RESOURCE_GROUP"),
            sandbox_group=_required("AZURE_SANDBOX_GROUP"),
            region=_required("AZURE_REGION"),
        )


class SandboxSession(Protocol):
    """The operations tools may use. Any object with these methods works."""

    def exec(self, command: str, working_directory: str | None = None) -> Any: ...
    def read_file(self, path: str) -> bytes: ...
    def write_file(self, path: str, content: str) -> None: ...


class SandboxProvider(Protocol):
    """Yields a ready sandbox for the duration of one run, then cleans it up."""

    def session(self, spec: SandboxSpec) -> AbstractContextManager[SandboxSession]: ...


class AzureSandboxProvider:
    """Creates a real sandbox in an Azure sandbox group via the preview SDK."""

    def __init__(self, settings: SandboxSettings, credential: Any | None = None):
        self._settings = settings
        if credential is None:
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
        self._credential = credential

    @contextmanager
    def session(self, spec: SandboxSpec) -> Iterator[SandboxSession]:
        from azure.containerapps.sandbox import SandboxGroupClient, endpoint_for_region

        s = self._settings
        group = SandboxGroupClient(
            endpoint_for_region(s.region),
            self._credential,
            subscription_id=s.subscription_id,
            resource_group=s.resource_group,
            sandbox_group=s.sandbox_group,
        )
        sandbox = None
        try:
            sandbox = group.begin_create_sandbox(
                disk=spec.disk,
                cpu=spec.cpu,
                memory=spec.memory,
                auto_suspend_seconds=spec.auto_suspend_seconds,
                labels={"app": LABEL_APP},
            ).result()
            yield sandbox
        finally:
            if sandbox is not None:
                try:
                    sandbox.delete()
                except Exception:
                    log.exception("Failed to delete sandbox; it will auto-suspend/expire")
            group.close()


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing environment variable {name} (see .env.example)")
    return value
